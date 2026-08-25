pipeline {
    agent any

    environment {
        IMAGE = "192.168.152.131:5000/root/demo-app/demo-app"
        TAG = "${BUILD_NUMBER}"
    }

    stages {
        stage('Build Image') {
            steps {
                sh "docker build -t ${IMAGE}:${TAG} ."
            }
        }
        stage('Push Image') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'gitlab-git',
                    usernameVariable: 'REG_USER', passwordVariable: 'REG_PASS')]) {
                    sh "echo ${REG_PASS} | docker login 192.168.152.131:5000 -u ${REG_USER} --password-stdin"
                    sh "docker push ${IMAGE}:${TAG}"
                }
            }
        }
        stage('Deploy K8s') {
            steps {
                sh """
                sed -i 's|IMAGE_PLACEHOLDER|${IMAGE}:${TAG}|g' k8s/deployment.yaml
                kubectl apply -f k8s/
                kubectl rollout status deployment/demo-app --timeout=90s
                """
            }
        }
    }
}
