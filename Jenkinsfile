pipeline {
    agent any

    options {
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
        ansiColor('xterm')
        timestamps()
    }

    environment {
        COMPOSE_FILE = 'docker-compose.yml'
        APP_URL      = 'http://localhost'
        PROJECT_NAME = 'canvas-drawer'
    }

    parameters {
        choice(name: 'DEPLOY_ENV', choices: ['production', 'staging'], description: 'Target deployment environment')
        booleanParam(name: 'RUN_TESTS', defaultValue: true, description: 'Run automated backend & frontend tests')
        booleanParam(name: 'CLEAN_DEPLOY', defaultValue: false, description: 'Perform fresh restart of containers')
    }

    stages {
        stage('1. Checkout SCM') {
            steps {
                echo "=========================================================="
                echo "Stage 1: Checking out source code repository"
                echo "Commit: ${env.GIT_COMMIT ?: 'Local Workspace'}"
                echo "Branch: ${env.GIT_BRANCH ?: 'main'}"
                echo "=========================================================="
                checkout scm
            }
        }

        stage('2. Static Code Analysis & Linting') {
            parallel {
                stage('Backend Python Validation') {
                    steps {
                        echo "Validating Python syntax and compiling bytecode..."
                        sh '''
                            python3 -m compileall CanvasDrawerProject/
                        '''
                    }
                }
                stage('Frontend TypeScript Check') {
                    steps {
                        echo "Validating Frontend TypeScript compilation..."
                        dir('Drawer') {
                            sh '''
                                if [ -d "node_modules" ]; then
                                    npm run build
                                else
                                    npm install && npm run build
                                fi
                            '''
                        }
                    }
                }
            }
        }

        stage('3. Run Automated Tests') {
            when {
                expression { return params.RUN_TESTS == true }
            }
            steps {
                echo "=========================================================="
                echo "Stage 3: Running Django test suite (auth, invite code, WS)"
                echo "=========================================================="
                sh '''
                    if [ -f "/home/noor/Projects/CanvasDrawer/bin/python" ]; then
                        cd CanvasDrawerProject && /home/noor/Projects/CanvasDrawer/bin/python manage.py test
                    else
                        cd CanvasDrawerProject && python3 manage.py test
                    fi
                '''
            }
        }

        stage('4. Validate & Build Docker Cluster') {
            steps {
                echo "=========================================================="
                echo "Stage 4: Validating docker-compose.yml and building images"
                echo "=========================================================="
                sh '''
                    docker compose -f ${COMPOSE_FILE} config
                    docker compose -f ${COMPOSE_FILE} build
                '''
            }
        }

        stage('5. Deploy 3-Replica Cluster via Nginx') {
            steps {
                echo "=========================================================="
                echo "Stage 5: Deploying Nginx Load Balancer & 3 Backend Replicas"
                echo "Environment: ${params.DEPLOY_ENV}"
                echo "=========================================================="
                sh '''
                    if [ "${params.CLEAN_DEPLOY}" = "true" ]; then
                        echo "Performing clean container teardown..."
                        docker compose -f ${COMPOSE_FILE} down
                    fi

                    chmod +x scripts/deploy.sh
                    ./scripts/deploy.sh ${COMPOSE_FILE}
                '''
            }
        }

        stage('6. Smoke Test & Health Check') {
            steps {
                echo "=========================================================="
                echo "Stage 6: Verifying Nginx and 3-Replica cluster health"
                echo "=========================================================="
                sh '''
                    chmod +x scripts/healthcheck.sh
                    ./scripts/healthcheck.sh ${APP_URL}
                '''
            }
        }
    }

    post {
        always {
            echo "=========================================================="
            echo "Pipeline run completed for build #${env.BUILD_NUMBER}"
            echo "=========================================================="
        }
        success {
            echo "SUCCESS: 3-Replica CanvasDrawer architecture successfully deployed behind Nginx!"
            sh '''
                docker compose -f ${COMPOSE_FILE} ps
            '''
        }
        failure {
            echo "FAILURE: Deployment or tests failed. Inspecting container logs:"
            sh '''
                docker compose -f ${COMPOSE_FILE} logs --tail=100 || true
            '''
        }
    }
}

