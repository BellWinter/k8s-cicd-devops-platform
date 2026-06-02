# 云原生微服务 CI/CD 自动化运维平台

  面向微服务场景搭建的云原生 CI/CD 自动化运维平台，实现应用容器化部署、自动化发布、服务治理及可观测能力。

  ## 项目架构

  ┌─────────────────────────────────────────────────────────────┐
  │                    云原生 CI/CD 平台                          │
  │                                                             │
  │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐│
  │  │  GitHub   │ →  │ Jenkins  │ →  │  Docker  │ →  │   K8s  ││
  │  │  代码仓库  │    │  流水线   │    │  镜像构建  │    │ 集群部署 ││
  │  └──────────┘    └──────────┘    └──────────┘    └────────┘│
  │                                                      ↓      │
  │                                              ┌──────────┐   │
  │                                              │ Traefik  │   │
  │                                              │ Ingress  │   │
  │                                              └──────────┘   │
  │  ┌──────────┐                              ┌──────────┐     │
  │  │ Grafana  │ ← ── ── ── ── ── ── ── ── ── │Prometheus │     │
  │  │  可视化   │        监控数据               │  指标采集  │     │
  │  └──────────┘                              └──────────┘     │
  └─────────────────────────────────────────────────────────────┘

  ## 技术栈

  | 组件 | 技术 | 作用 |
  |------|------|------|
  | 容器运行时 | Docker / containerd | 应用容器化 |
  | 容器编排 | Kubernetes | 集群管理与调度 |
  | CI/CD | Jenkins Pipeline | 自动化构建与部署 |
  | 应用框架 | Flask | Python 微服务应用 |
  | 服务暴露 | Traefik Ingress | 域名路由与流量转发 |
  | 监控采集 | Prometheus | 指标采集与存储 |
  | 监控展示 | Grafana | 可视化 Dashboard |
  | 代码管理 | GitHub | 代码托管与版本控制 |

  ## 项目功能

  ### 1. 应用容器化
  - 使用 Python Flask 编写微服务应用
  - 编写 Dockerfile 实现应用容器化
  - 支持多版本镜像管理（build-N）

  ### 2. CI/CD 自动化
  - Jenkins Pipeline as Code 声明式流水线
  - 自动化流程：拉取代码 → 单元测试 → 构建镜像 → 导入 K8s → 部署 → 验证
  - 支持滚动更新与版本发布

  ### 3. Kubernetes 编排
  - Deployment：应用部署与副本管理
  - Service：服务发现与负载均衡
  - Ingress：域名路由与流量入口
  - 健康检查：livenessProbe / readinessProbe

  ### 4. 可观测性
  - Prometheus：节点与应用指标采集
  - Grafana：可视化监控 Dashboard
  - 覆盖 CPU、内存、磁盘、网络等维度

  ## 快速开始

  ### 环境要求
  - Linux（Ubuntu 22.04）
  - Docker
  - Kubernetes（kubeadm）
  - Jenkins

  ### 部署步骤

  ```bash
  # 1. 克隆项目
  git clone https://github.com/BellWinter/k8s-cicd-devops-platform.git
  cd k8s-cicd-devops-platform

  # 2. 构建 Docker 镜像
  docker build -t demo-app:v1.0 .

  # 3. 导入镜像到 K8s
  docker save demo-app:v1.0 | ctr -n k8s.io images import -

  # 4. 部署到 K8s
  kubectl apply -f k8s-deployment.yaml
  kubectl apply -f k8s-service.yaml
  kubectl apply -f k8s-ingress.yaml

  # 5. 验证部署
  kubectl get pods -l app=demo-app
  curl http://localhost:31000/health

  访问地址

  ┌────────────┬────────────────────────────┐
  │    服务    │            地址            │
  ├────────────┼────────────────────────────┤
  │ 应用       │ http://localhost:31000     │
  ├────────────┼────────────────────────────┤
  │ Jenkins    │ http://jenkins.local:30595 │
  ├────────────┼────────────────────────────┤
  │ Prometheus │ http://localhost:30090     │
  ├────────────┼────────────────────────────┤
  │ Grafana    │ http://localhost:30030     │
  └────────────┴────────────────────────────┘

  项目文件说明

  ├── app.py                  # Flask 应用代码
  ├── test_app.py             # 单元测试
  ├── requirements.txt        # Python 依赖
  ├── Dockerfile              # Docker 容器化配置
  ├── Jenkinsfile             # Jenkins Pipeline 流水线配置
  ├── k8s-deployment.yaml     # Kubernetes Deployment 配置
  ├── k8s-service.yaml        # Kubernetes Service 配置
  └── k8s-ingress.yaml        # Kubernetes Ingress 配置

  排错记录

  1. K8s 集群搭建

  - Swap 未关闭导致 kubelet 启动失败
  - 镜像源不可用，配置阿里云镜像加速
  - sandbox 镜像配置问题导致容器无法启动

  2. Jenkins Pipeline

  - Groovy 语法与 sed 命令冲突
  - Jenkins 容器缺少 docker/ctr 命令
  - Docker socket 权限问题

  3. 监控平台

  - Prometheus 无法解析主机名，改用 IP 地址
  - node-exporter 未安装导致无指标数据

  联系方式

  - GitHub：BellWinter (https://github.com/BellWinter)
  - 项目链接：k8s-cicd-devops-platform (https://github.com/BellWinter/k8s-cicd-devops-platform)
