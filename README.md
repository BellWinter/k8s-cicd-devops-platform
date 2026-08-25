# 云原生 CI/CD 自动化部署平台

把 GitLab、Jenkins、GitLab Container Registry 和 Kubernetes 串起来做的一个自动化部署项目。代码推到 GitLab 的 main 分支后，剩下的构建、推镜像、部署到集群全部自动完成，不用人管。

## 架构

整个链路是这样的：

```
GitLab 收到 push
  → Webhook 通知 Jenkins
  → Jenkins 拉代码、构建镜像
  → 推到 GitLab Container Registry（192.168.152.131:5000）
  → kubectl apply 部署到 K8s
  → 滚动更新完成
```

部署 demo-app 是 nginx 静态页，2 个副本，通过 NodePort 30081 访问。

各组件：

| 组件 | 地址 | 说明 |
|---|---|---|
| GitLab CE | 192.168.152.131:8000 | Docker 部署，代码托管 + webhook 触发 |
| Jenkins | 192.168.152.131:8080 | Docker 部署，挂载宿主机 docker.sock |
| Container Registry | 192.168.152.131:5000 | GitLab 内置 registry（HTTP） |
| Kubernetes | kubeadm 1.28.15 + flannel | containerd 2.x 运行时 |
| demo-app | 192.168.152.131:30081 | nginx 静态页，2 副本 |

## 流水线

Jenkinsfile 是声明式流水线，三个阶段：

1. **Build Image**：`docker build`，镜像 tag 用构建号（`demo-app:${BUILD_NUMBER}`）
2. **Push Image**：`docker login` 登录私有仓库后 push（凭据走 Jenkins Credentials）
3. **Deploy K8s**：用 `sed` 把 deployment.yaml 里的 `IMAGE_PLACEHOLDER` 替换成实际镜像版本，`kubectl apply` 后等滚动更新完成

部署阶段的核心逻辑：

```groovy
stage('Deploy K8s') {
    steps {
        sh """
        sed -i 's|IMAGE_PLACEHOLDER|${IMAGE}:${TAG}|g' k8s/deployment.yaml
        kubectl apply -f k8s/
        kubectl rollout status deployment/demo-app --timeout=90s
        """
    }
}
```

镜像地址规则：`192.168.152.131:5000/root/demo-app/demo-app:<构建号>`，每次构建版本自动递增。

## 目录

```
├── Dockerfile          # nginx 镜像，用 DaoCloud 加速源
├── Jenkinsfile         # 三阶段流水线
├── index.html          # 应用页面
├── k8s/
│   └── deployment.yaml # Deployment（含 regcred）+ Service（NodePort）
└── docs/
    └── troubleshooting.md  # 部署过程中踩过的坑，24 条
```

## 部署时的一些配置

这套环境是内网（192.168.152.131），registry 走 HTTP，所以有几处必须配置的地方：

**GitLab gitlab.rb**（追加后 reconfigure）：

```ruby
registry_external_url "http://192.168.152.131:5000"
registry_nginx["enable"] = false
external_url "http://192.168.152.131:8000"
nginx["listen_port"] = 80
```

注意 reconfigure 会把 registry 的监听地址重置回 127.0.0.1，需要重新改：

```bash
sed -i 's|addr: 127.0.0.1:5000|addr: 0.0.0.0:5000|' /var/opt/gitlab/registry/config.yml
gitlab-ctl restart registry
```

**containerd**（K8s 拉 HTTP registry 镜像）：

`/etc/containerd/config.toml` 里 `config_path` 必须是单目录：

```toml
config_path = '/etc/containerd/certs.d'
```

`/etc/containerd/certs.d/192.168.152.131:5000/hosts.toml`：

```toml
server = "http://192.168.152.131:5000"
```

这里踩过一个大坑：containerd 2.x 默认的 config_path 是 `certs.d:/etc/docker/certs.d` 这种 Docker 风格的写法，containerd 只认单目录，导致 hosts.toml 一直不生效，拉镜像报 HTTPS 错误。

**Docker daemon**（Jenkins push 镜像用）：

```json
{"registry-mirrors": ["https://docker.m.daocloud.io"], "insecure-registries": ["192.168.152.131:5000"]}
```

**Jenkins 任务**：触发器勾"Build when a change is pushed to GitLab"；授权用项目级矩阵，给 Anonymous 开 Job/Build 权限（GitLab 插件的 webhook 端点不走 CSRF，但需要这个权限）。

**GitLab webhook**：URL 填 `http://192.168.152.131:8080/project/demo-app`，只勾 Push events。另外 GitLab 默认拦内网 IP 的 webhook（SSRF 防护），要在 Admin -> Settings -> Network -> Outbound requests 里放行本地网络，否则 URL 都提交不上去。

## 排障记录

部署过程中踩了不少坑，都记在 [docs/troubleshooting.md](docs/troubleshooting.md) 里了，一共 24 条，每条都是"现象 -> 根因 -> 方案"。比较典型的几个：

- GitLab 网页创建 webhook 一直报 Invalid url，实际是 SSRF 拦了内网 IP
- Jenkins 403 有两次，一次是缺匿名 Build 权限，一次是 CSRF crumb（换用 GitLab 插件端点解决）
- registry 进程看着在跑，但 5000 端口根本没监听，restart 才恢复
- containerd 2.x 的 config_path 只接受单目录，Docker 风格写法直接失效

## 验证

```bash
# push 代码后自动部署，访问应用
curl http://192.168.152.131:30081

# 看部署状态
kubectl get deployment demo-app
kubectl rollout status deployment/demo-app
```

## 环境

单节点 K8s（Master：192.168.152.131，VMware + Ubuntu 22.04，16G 内存）。国内网络环境，所有镜像源都换成了 DaoCloud / 清华源。
