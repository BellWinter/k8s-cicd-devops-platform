  pipeline {
      agent any

      environment {
          APP_NAME = "demo-app"
          DOCKER_IMAGE = "demo-app:${BUILD_NUMBER}"
          K8S_NAMESPACE = "default"
      }

      stages {
          stage('拉取代码') {
              steps {
                  echo "正在拉取代码..."
                  checkout scm
                  echo "代码拉取完成"
              }
          }

          stage('单元测试') {
              steps {
                  echo "正在执行单元测试..."
                  sh 'pip install flask pytest -q'
                  sh 'python -m pytest test_app.py -v'
                  echo "测试通过"
              }
          }

          stage('构建镜像') {
              steps {
                  echo "正在构建 Docker 镜像: ${DOCKER_IMAGE}..."
                  sh "docker build -t ${DOCKER_IMAGE} ."
                  sh "docker tag ${DOCKER_IMAGE} ${APP_NAME}:latest"
                  echo "镜像构建完成"
              }
          }

          stage('部署到K8s') {
              steps {
                  echo "正在部署到 Kubernetes..."
                  sh "kubectl apply -f k8s-deployment.yaml"
                  sh "kubectl apply -f k8s-service.yaml"
                  sh "kubectl apply -f k8s-ingress.yaml"
                  echo "部署完成"
              }
          }

          stage('验证部署') {
              steps {
                  echo "正在验证部署状态..."
                  sh "kubectl rollout status deployment/${APP_NAME} -n ${K8S_NAMESPACE} --timeout=60s"
                  sh "kubectl get pods -l app=${APP_NAME} -n ${K8S_NAMESPACE}"
                  echo "验证完成"
              }
          }

          stage('更新版本') {
              steps {
                  echo "正在更新应用版本..."
                  sh """
                      sed -i 's|image: ${APP_NAME}:.*|image: ${APP_NAME}:${BUILD_NUMBER}|' k8s-deployment.yaml
                      sed -i 's|value: ".*"|value: "build-${BUILD_NUMBER}"|' k8s-deployment.yaml
                      kubectl apply -f k8s-deployment.yaml
                  """
                  echo "版本更新完成"
              }
          }
      }

      post {
          success {
              echo "Pipeline 执行成功！应用: ${APP_NAME}, 版本: #${BUILD_NUMBER}"
          }
          failure {
              echo "Pipeline 执行失败，请检查日志"
          }
      }
  }
