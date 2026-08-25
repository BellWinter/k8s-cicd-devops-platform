# ☁️ K8s 云原生项目部署排障全记录

> **项目**：GitLab + Jenkins + GitLab Container Registry + Kubernetes 自动构建部署（CI/CD 全链路）
> **环境**：VMware Workstation + Ubuntu 22.04 + 1 Master（192.168.152.131，16GB 内存）
> **周期**：2026-08-19 ~ 2026-08-21
> **最终状态**：push 代码 → Jenkins 自动构建 → 推送镜像 → K8s 滚动部署，全流程 SUCCESS ✅

---

## 一、架构总览

```text
开发者 push 代码
    ↓
GitLab (192.168.152.131:8000, Docker 容器)
    ↓ Webhook (GitLab 插件端点 /project/demo-app)
Jenkins (192.168.152.131:8080, Docker 容器, 挂载宿主机 docker.sock)
    ↓ 1. checkout 拉代码
    ↓ 2. docker build 构建镜像
    ↓ 3. docker login + push
GitLab Container Registry (192.168.152.131:5000, GitLab 内置)
    ↓
Kubernetes 集群 (kubeadm v1.28.15 + flannel, containerd 2.x)
    ↓ kubectl apply + rollout
demo-app Deployment (2 副本, NodePort 30081) ✅
```

| 组件 | 地址 | 部署方式 |
|---|---|---|
| GitLab CE | `http://192.168.152.131:8000` | Docker 容器（`-p 8000:80 -p 5000:5000`） |
| Jenkins LTS | `http://192.168.152.131:8080` | Docker 容器（`-u root`，挂载 `/var/run/docker.sock`） |
| GitLab Container Registry | `http://192.168.152.131:5000` | GitLab 内置 registry 服务 |
| Kubernetes | `kubeadm v1.28.15` + flannel | containerd 2.x 运行时 |
| demo-app | `http://192.168.152.131:30081` | Deployment + NodePort Service |

---

## 二、问题与解决一览表（速查版）

| # | 阶段 | 问题现象 | 根因 | 解决方案 |
|---|---|---|---|---|
| 1 | 系统初始化 | apt update 被劫持到 `1.1.1.3 disable.htm` | 运营商/校园网 HTTP 劫持 | 改用 **HTTPS 清华源** |
| 2 | 系统初始化 | `raw.githubusercontent.com` 无法下载 | GitHub 被墙 | 用 **jsdelivr CDN** 下载 flannel 清单 |
| 3 | 集群搭建 | 业务镜像拉取走不了 mirror 加速 | `ctr` 不走 CRI mirror 配置 | 镜像直接用**完整加速地址** `docker.m.daocloud.io/xxx` |
| 4 | 集群搭建 | Pod 无法调度到 master | master 有 `NoSchedule` 污点 | `kubectl taint` 移除污点 |
| 5 | Ingress | ingress-nginx 镜像拉取 TLS 超时 | 镜像源不稳定 | 换 `k8s.m.daocloud.io` + 重试 |
| 6 | 滚动更新 | 坏版本 9.9.9 更新卡住 | 镜像不存在拉取失败 | `kubectl rollout undo` 秒级回滚 |
| 7 | GitLab 部署 | Puma worker 启动超时被杀，CPU 100% | 容器 `--memory=2g` 硬限制，内存 99.98% | `docker update --memory=4g` + restart |
| 8 | GitLab 部署 | `--memory=0` 无法取消内存限制 | Docker 特性 | 必须**显式给更大值** |
| 9 | GitLab 部署 | 创建 PAT 的 UI 按钮缺失 | 版本 UI 问题 | `gitlab-rails runner` 命令创建 |
| 10 | 镜像仓库 | Harbor 安装包下载全部失败 | GitHub Release 全部被墙 | **放弃 Harbor，改用 GitLab 内置 Container Registry** |
| 11 | 镜像仓库 | registry 监听 `127.0.0.1:5000` 外部连不上 | `registry['listen_addr']` 配置键在 GitLab 17 **不生效** | `sed` 改 config.yml 的 addr + `gitlab-ctl restart registry` |
| 12 | 镜像仓库 | reconfigure 后 registry 又变回 127.0.0.1 | **每次 reconfigure 重置 config.yml** | 每次 reconfigure 后必须重新 sed + restart |
| 13 | 镜像仓库 | nginx 与 registry 抢 5000 端口 | registry_nginx 默认启用 | `registry_nginx["enable"] = false` |
| 14 | 镜像仓库 | docker login 报认证 realm 指向 :80 连不上 | external_url 未带端口 | `external_url "http://192.168.152.131:8000"` + `nginx["listen_port"] = 80` |
| 15 | 镜像仓库 | 容器没有 5000 端口映射 | 创建时未加 `-p 5000:5000` | 重建容器加端口映射 |
| 16 | K8s 拉镜像 | `http: server gave HTTP response to HTTPS client` | containerd 2.x 的 `config_path` **只接受单目录**，`: 分隔多目录`整条失效 | `sed` 把 config_path 改为单目录 + `systemctl restart containerd` |
| 17 | 集群健康 | 节点 disk-pressure | 磁盘被 swap.img (2.9G) 占用 | 删除 swap.img 释放空间 |
| 18 | 集群健康 | flannel subnet.env 丢失，网络异常 | 内核更新后 `br_netfilter` 未加载 | `modprobe br_netfilter` |
| 19 | Webhook | GitLab 网页创建报 `Invalid url given` | **SSRF 保护拦截内网 IP**（非输入问题） | Admin → Settings → Network → Outbound requests 放行本地网络 |
| 20 | Webhook | rails runner 报 `event not found` | bash 历史扩展把 `!` 当命令引用 | Ruby 代码里用 `h.save` 代替 `h.save!` |
| 21 | Webhook | Jenkins 403 `anonymous is missing the Job/Build permission` | GitLab 插件端点需匿名 Build 权限 | 项目授权矩阵给 **Anonymous → Job → Build** |
| 22 | Webhook | Jenkins 403 `No valid crumb was included` | 远程触发端点绕不开 CSRF crumb | **改用 GitLab 插件端点 `/project/demo-app`（免 crumb）** |
| 23 | Webhook | registry connection refused | registry 进程"假活"，容器内 5000 无监听 | `gitlab-ctl restart registry` 恢复监听 |
| 24 | Webhook | Docker push 报 HTTPS 错误（预期坑） | HTTP registry 需要声明 | `daemon.json` 配 `insecure-registries`（早已配好） |

---

## 三、详细排障记录

### 3.1 系统初始化阶段（08-19）

**问题 1：apt 源被劫持**

- **现象**：`apt update` 指向 `1.1.1.3 disable.htm`，拉取的全是劫持页面
- **根因**：运营商/校园网对 HTTP 流量做 DNS 劫持或透明代理
- **解决**：编辑 `/etc/apt/sources.list` 换成 **HTTPS 清华源**
  ```bash
  sed -i 's|http://|https://|g' /etc/apt/sources.list
  ```

**问题 2：GitHub 资源下载被墙**

- **现象**：`raw.githubusercontent.com` 超时无法下载 flannel 清单
- **解决**：改用 **jsdelivr CDN** 镜像下载，flannel 镜像地址替换为 `ghcr.m.daocloud.io`

**问题 3：镜像加速不生效**

- **现象**：`ctr` 拉镜像不走 CRI mirror 配置
- **解决**：业务镜像直接写**完整加速地址** `docker.m.daocloud.io/nginx:latest`，不依赖 mirror 配置

**问题 4：master 节点无法调度 Pod**

- **现象**：Pod 一直 Pending
- **根因**：master 自带 `NoSchedule` 污点
- **解决**：单节点环境移除污点
  ```bash
  kubectl taint nodes --all node-role.kubernetes.io/control-plane-
  ```

### 3.2 Ingress 与滚动更新（08-20）

**问题 5：ingress-nginx 镜像拉取超时**

- **解决**：换 `k8s.m.daocloud.io` 镜像源，重试后成功
- 配套：NodePort 入口 Service（30080/30443）+ Ingress 规则（`demo.local` → nginx-demo:80）+ Windows hosts 解析

**问题 6：滚动更新/回滚演练**

- 升级 nginx 1.25.5 → 坏版本 9.9.9（镜像不存在）→ rollout 卡住
- **`kubectl rollout undo deployment/nginx-demo` 秒级回滚成功**
- 这是面试必讲的 K8s 自愈/回滚能力案例

### 3.3 GitLab 容器部署（08-20）

**问题 7：内存限制导致 GitLab 启动失败**

- **现象**：MEM 99.98%，Puma worker 60s 启动超时被杀，CPU 持续 100%+
- **根因**：容器 `--memory=2g` 硬限制，GitLab 全家桶需要约 3.4GiB
- **解决**：
  ```bash
  docker update --memory=4g --memory-swap=4g gitlab
  docker restart gitlab
  ```
- 修复后 CPU 降至 11%，MEM 3.4GiB/4GiB

**问题 8：`--memory=0` 不能取消限制**

- 教训：Docker 里 `--memory=0` 不是"无限"，**必须显式给一个更大的值**

**问题 9：创建 Personal Access Token（PAT）**

- 版本 UI 缺按钮 → 用 `gitlab-rails runner` 命令创建（绕过 UI）

### 3.4 镜像仓库：Harbor 受阻 → GitLab Container Registry（08-20）

**问题 10：Harbor 放弃**

- GitHub Release 全被墙：gh-proxy.com 截断 11KB、ghfast.top 空文件、gh.llkk.cc 拒绝连接
- **决策**：放弃 Harbor，改用 **GitLab 内置 Container Registry**（`registry_external_url='http://192.168.152.131:5000'`）

**问题 11：registry 监听地址不生效（最坑的一个）**

- **现象**：`docker login 192.168.152.131:5000` connection refused
- **根因**：`registry['listen_addr'] = "0.0.0.0:5000"` 配置键在 **GitLab 17 不生效**，config.yml 仍生成 `127.0.0.1:5000`
- **解决**（直接改生成的配置文件）：
  ```bash
  sed -i 's|addr: 127.0.0.1:5000|addr: 0.0.0.0:5000|' /var/opt/gitlab/registry/config.yml
  gitlab-ctl restart registry
  ```

**问题 12：reconfigure 会重置 addr（必须重复操作）**

- 每次 `gitlab-ctl reconfigure` 都会**重新生成** config.yml，把 addr 改回 127.0.0.1
- 结论：**reconfigure 后必须重新 sed + restart registry**，建议写成脚本固化

**问题 13：nginx 与 registry 抢端口**

- 不加 `registry_nginx["enable"] = false` 时，nginx 会和 registry 抢 5000 端口
- gitlab.rb 追加：
  ```ruby
  registry_external_url "http://192.168.152.131:5000"
  registry_nginx["enable"] = false
  external_url "http://192.168.152.131:8000"
  nginx["listen_port"] = 80   # external_url 带端口会改 nginx 监听，必须锁回 80 对应 -p 8000:80
  ```

**问题 14：registry 认证 realm 指向错误端口**

- **现象**：`docker login` 后认证跳转 `http://...:80/jwt/auth` 连不上
- **根因**：`external_url` 没带端口 8000
- **解决**：`external_url "http://192.168.152.131:8000"` + `nginx["listen_port"] = 80`

**问题 15：容器端口映射缺失**

- 必须 `-p 5000:5000` 映射（重建容器时补上）

**验证通过**：`curl http://127.0.0.1:5000/v2/` 返回 401；`docker login 192.168.152.131:5000`（root + GitLab 密码）Succeeded

### 3.5 containerd 配置 HTTP registry（08-21）

**问题 16：K8s 拉私有镜像报 HTTPS 错误**

- **现象**：`http: server gave HTTP response to HTTPS client`，即使 hosts.toml 已配置
- **根因**：containerd 2.x 的 `[plugins.'io.containerd.cri.v1.images']` 节下，默认 `config_path = '/etc/containerd/certs.d:/etc/docker/certs.d'` 是 **Docker 风格冒号分隔多目录**，而 containerd 的 `config_path` **只接受单个目录** → 整个路径无效 → hosts.toml 不被读取 → 回退 HTTPS
- **解决**：
  ```bash
  sudo sed -i "s|config_path = '/etc/containerd/certs.d:/etc/docker/certs.d'|config_path = '/etc/containerd/certs.d'|" /etc/containerd/config.toml
  sudo systemctl restart containerd
  ```
- **hosts.toml 结构**（`/etc/containerd/certs.d/192.168.152.131:5000/hosts.toml`）：
  ```toml
  server = "http://192.168.152.131:5000"
  ```
- **验证注意**：`crictl pull` 是匿名的，私有仓库报 403 Forbidden 属正常；Pod 用 `imagePullSecrets(regcred)` 带凭据拉取不受影响

### 3.6 集群健康问题（08-21 早）

**问题 17：disk-pressure**

- **解决**：删除 swap.img（2.9G）释放空间

**问题 18：flannel subnet.env 丢失**

- **现象**：内核更新后网络插件异常
- **根因**：`br_netfilter` 内核模块未加载
- **解决**：`modprobe br_netfilter`（并写入 `/etc/modules-load.d/` 持久化）

### 3.7 Webhook 自动触发排障（08-21 下午，最长的战斗）

**问题 19：GitLab 网页创建 webhook 报 `Invalid url given`**

- 用户输入 URL 完全正确（截图确认无全角字符问题），但网页一直拒绝
- **根因**：现代 GitLab 默认**禁止 webhook 请求内网/私有 IP**（SSRF 防护），`192.168.152.131` 是私网地址 → 服务器端校验直接判 Invalid
- **诊断确认**（命令行创建 webhook 看真实报错）：
  ```bash
  sudo docker exec gitlab gitlab-rails runner "p = Project.find_by_full_path('root/demo-app'); h = p.hooks.new(url: 'http://192.168.152.131:8080/project/demo-app', push_events: true, enable_ssl_verification: false); puts 'valid=' + h.valid?.to_s; puts h.errors.full_messages.join(' | ')"
  # 输出：Url is blocked: Requests to the local network are not allowed
  ```
- **解决**：Admin Area → **Settings → Network → Outbound requests**
  1. 勾选 ☑️ `Allow requests to the local network from webhooks and integrations`
  2. 白名单填 `192.168.152.131`
  3. **Save changes 立即生效，无需 reconfigure**

> ⚠️ 坑：命令行改 `gitlab_rails['outbound_local_requests_allowlist']` 报 undefined method —— 该 GitLab 版本较老没有此设置项，**UI 勾选框才是正确入口**

**问题 20：rails runner 命令的 bash 历史扩展坑**

- **现象**：`h.save!` 里的 `!` 被 bash 当成历史命令引用 → `event not found`
- **解决**：Ruby 代码里避免 `!`，用 `h.save` 代替 `h.save!`

**问题 21：Jenkins 403 `anonymous is missing the Job/Build permission`**

- 场景：GitLab 插件端点 `/project/demo-app` 收到请求但被权限拒绝
- **解决**：Manage Jenkins → Security → Authorization → **Matrix-based security（项目级）**，给 **Anonymous** 勾选 **Job → Build**，保存

**问题 22：Jenkins 403 `No valid crumb was included in the request`**

- 场景：改用远程触发端点 `/job/demo-app/build?token=xxx` 后
- **根因**：新版 Jenkins 的 CSRF crumb 保护，远程触发端点也绕不开
- **正确路线**：**不要走远程触发 token，用 GitLab 插件自己的端点** `/project/demo-app`（免 crumb），配合匿名 Build 权限即可

**问题 23：GitLab Container Registry connection refused（复现）**

- **现象**：宿主机 `curl 192.168.152.131:5000/v2/` refused；`gitlab-ctl status` 显示 registry run；容器内 `ss/netstat` 无 5000 监听
- **根因**：registry 进程"假活"——进程在跑但 HTTP 监听未生效（reconfigure 重置配置后的遗留状态）
- **解决**：`gitlab-ctl restart registry` → 监听恢复 → curl 返回 401 ✅
- **排查路径参考**（可复用的诊断三板斧）：
  1. 宿主机 curl → refused
  2. 容器内 `netstat -tln | grep 5000` → 无监听（进程活着≠服务在监听）
  3. `gitlab-ctl restart registry` → 恢复

**问题 24：Docker push HTTP registry**

- **现象**（预期内）：docker 默认拒绝 HTTP registry
- **解决**：`/etc/docker/daemon.json` 配 `insecure-registries: ["192.168.152.131:5000"]`（本项目早已配好，无需改动）

### 3.8 最终验证（08-21 17:08）

```text
Started by GitLab push by Bell Winter
docker build -t 192.168.152.131:5000/root/demo-app/demo-app:7 .   ✅
docker login 192.168.152.131:5000 → Login Succeeded            ✅
docker push .../demo-app:7 → digest 推送成功                    ✅
kubectl apply -f k8s/ → deployment.apps/demo-app configured      ✅
kubectl rollout status deployment/demo-app → successfully rolled out ✅
Finished: SUCCESS
```

**现在：GitLab 任意 push 到 main → 全链路自动构建部署，零人工干预。**

---

## 四、关键配置速查

### GitLab webhook
- URL：`http://192.168.152.131:8080/project/demo-app`（**GitLab 插件端点，不是 /job/ 路径**）
- 触发：仅 Push events；Secret token 留空
- 前置：Admin → Network → Outbound requests 勾选"允许本地网络请求"

### Jenkins 任务（demo-app）
- 触发器：☑️ `Build when a change is pushed to GitLab` + Push Events（此版本插件无 Secret token 字段）
- 授权：项目级矩阵，Anonymous → Job → Build
- 凭据：`gitlab-git`（拉代码）、`REG_PASS`（registry 密码，root 的 GitLab 密码）

### GitLab gitlab.rb（registry 相关）
```ruby
registry_external_url "http://192.168.152.131:5000"
registry_nginx["enable"] = false
external_url "http://192.168.152.131:8000"
nginx["listen_port"] = 80
```
> reconfigure 后必须：`sed -i 's|addr: 127.0.0.1:5000|addr: 0.0.0.0:5000|' /var/opt/gitlab/registry/config.yml && gitlab-ctl restart registry`

### containerd（HTTP registry）
- `/etc/containerd/config.toml`：`config_path = '/etc/containerd/certs.d'`（**单目录，不能冒号分隔**）
- `/etc/containerd/certs.d/192.168.152.131:5000/hosts.toml`：
  ```toml
  server = "http://192.168.152.131:5000"
  ```

### Docker daemon
```json
{"registry-mirrors": ["https://docker.m.daocloud.io"], "insecure-registries": ["192.168.152.131:5000"]}
```

### 镜像路径规则
`192.168.152.131:5000/<namespace>/<project>/<image>:<tag>`（GitLab Container Registry 规则）

---

## 五、经验总结（方法论沉淀）

1. **"服务进程活着 ≠ 服务正常监听"** —— 排查连接失败时，先看监听地址（`ss/netstat`），再看进程状态，最后看日志
2. **端口映射 ≠ 端口可用** —— docker-proxy 监听 ≠ 容器内服务监听，要从容器内验证
3. **UI 报错信息可能误导** —— GitLab "Invalid url" 其实是 SSRF 安全策略，用命令行 runner 拿真实报错最准
4. **reconfigure 会覆盖手工修改** —— 生成式配置文件（config.yml）的手工改动要在 reconfigure 后重新应用，应固化成脚本
5. **被墙环境的镜像源策略** —— 所有外部下载优先 DaoCloud 镜像（`*.m.daocloud.io`）、jsdelivr CDN、清华/阿里源
6. **二选一时选"官方集成"** —— Harbor 下载受阻时，GitLab 内置 Container Registry 是零额外部署成本的替代
7. **containerd 2.x 与 Docker 配置差异大** —— `config_path` 单目录、`certs.d` 结构，不能用 Docker 思维套用
8. **CSRF/SSRF 是新版系统最常见的"隐形墙"** —— GitLab SSRF 拦内网 webhook、Jenkins crumb 拦远程触发，先了解安全模型再排障
9. **诊断三板斧**：先 curl 验证连通 → 再进容器看监听 → 最后看服务日志，避免盲猜
10. **bash 引号/历史扩展坑** —— rails runner 内嵌 Ruby 代码避免 `!`、用单引号包裹命令

---

*文档生成时间：2026-08-21 · 由部署全过程排障记录整理*
