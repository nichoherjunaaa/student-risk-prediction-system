pipeline {
    agent any

    options {
        timeout(time: 40, unit: 'MINUTES')
        disableConcurrentBuilds()
        timestamps()
    }

    triggers {
        // Fallback if the GitHub webhook is missed. The webhook itself is what
        // makes deploys near-instant (see DEPLOYMENT.md).
        pollSCM('H/5 * * * *')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Prepare env') {
            // Production secrets come from a Jenkins "Secret file" credential
            // (id: sisip-env), never from git. docker compose reads ./.env.
            steps {
                withCredentials([file(credentialsId: 'sisip-env', variable: 'ENV_FILE')]) {
                    sh 'cp "$ENV_FILE" .env'
                }
            }
        }

        stage('Build images') {
            // `docker compose build` streams the build context from the Jenkins
            // workspace to the Docker daemon, so it works even when Jenkins runs
            // in a container with the host docker socket mounted. The frontend
            // image runs `npm run build`, failing the pipeline on any real error.
            steps {
                sh 'docker compose build'
            }
        }

        stage('Deploy') {
            steps {
                sh 'docker compose up -d --remove-orphans'
            }
        }

        stage('Health check') {
            steps {
                sh '''
                    echo "Waiting for the stack to become healthy..."
                    for i in $(seq 1 36); do
                        if docker compose exec -T backend curl -fsS http://localhost:5000/api/health >/dev/null 2>&1; then
                            echo "Backend healthy."
                            docker compose exec -T frontend wget -qO- http://localhost/api/health
                            exit 0
                        fi
                        sleep 5
                    done
                    echo "Health check failed - recent logs:"
                    docker compose logs --tail=120
                    exit 1
                '''
            }
        }
    }

    post {
        always {
            sh 'rm -f .env'
        }
        success {
            sh 'docker image prune -f || true'
        }
        failure {
            sh 'docker compose ps || true'
        }
    }
}
