pipeline {
  agent any

  environment {
    // Image and container names
    IMAGE_NAME = "fastapi-postgres-app"
    IMAGE_TAG  = "${env.BUILD_ID}"
    FULL_IMAGE = "${IMAGE_NAME}:${IMAGE_TAG}"

    // Container names & network
    APP_CONTAINER = "fastapi-app"
    DB_CONTAINER  = "pg-db"
    DOCKER_NETWORK = "backend"

    // DB env (these will also be passed into docker run)
    POSTGRES_USER     = "appuser"
    POSTGRES_PASSWORD = "apppass"
    POSTGRES_DB       = "appdb"
    POSTGRES_PORT     = "5432"
    POSTGRES_HOST     = "${DB_CONTAINER}"

    // Optional: Docker registry (if you push images)
    DOCKER_REGISTRY = ""   // e.g. "myregistry.azurecr.io"
  }

  options {
    // Keep build logs for a while
    buildDiscarder(logRotator(numToKeepStr: '30'))
    timestamps()
  }

  stages {

    stage('Checkout') {
      steps {
        echo "Checking out source from Git"
        checkout scm
      }
    }

    stage('Build image') {
      steps {
        echo "Building Docker image ${FULL_IMAGE}"
        // Build image with Dockerfile in repo root
        sh '''
          docker build -t ${FULL_IMAGE} .
        '''
      }
    }

    stage('Optional: Push image to registry') {
      when {
        expression { return env.DOCKER_REGISTRY?.trim() }
      }
      steps {
        echo "Tagging and pushing image to registry"
        sh '''
          docker tag ${FULL_IMAGE} ${DOCKER_REGISTRY}/${FULL_IMAGE}
          # If using credentials, you must do docker login first (see credentials config)
          docker push ${DOCKER_REGISTRY}/${FULL_IMAGE}
        '''
      }
    }

    stage('Prepare network & DB') {
      steps {
        echo "Ensure docker network exists and DB container is running (persistent volume preserved)"
        // Create network if not exists, and ensure DB container running (won't reinitialize data if volume exists)
        sh '''
          if ! docker network ls --format '{{.Name}}' | grep -q "^${DOCKER_NETWORK}$"; then
            docker network create ${DOCKER_NETWORK}
          fi

          # If DB is already running, leave it (we want to preserve data). If not, create it.
          if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
            if docker ps -a --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
              docker start ${DB_CONTAINER}
            else
              docker run -d \
                --name ${DB_CONTAINER} \
                --network ${DOCKER_NETWORK} \
                -e POSTGRES_USER=${POSTGRES_USER} \
                -e POSTGRES_PASSWORD=${POSTGRES_PASSWORD} \
                -e POSTGRES_DB=${POSTGRES_DB} \
                -v /opt/postgres-data:/var/lib/postgresql/data \
                -p ${POSTGRES_PORT}:5432 \
                postgres:16
            fi
          fi
        '''
      }
    }

    stage('Stop old app & run new') {
      steps {
        echo "Stop and remove old app container (if exists), then start the new one"
        sh '''
          set -e
          if docker ps --format '{{.Names}}' | grep -q "^${APP_CONTAINER}$"; then
            docker stop ${APP_CONTAINER}
            docker rm ${APP_CONTAINER}
          elif docker ps -a --format '{{.Names}}' | grep -q "^${APP_CONTAINER}$"; then
            docker rm ${APP_CONTAINER}
          fi

          # Run the new app container attached to the same network
          docker run -d \
            --name ${APP_CONTAINER} \
            --network ${DOCKER_NETWORK} \
            -e POSTGRES_USER=${POSTGRES_USER} \
            -e POSTGRES_PASSWORD=${POSTGRES_PASSWORD} \
            -e POSTGRES_DB=${POSTGRES_DB} \
            -e POSTGRES_HOST=${POSTGRES_HOST} \
            -e POSTGRES_PORT=${POSTGRES_PORT} \
            -p 8000:8000 \
            ${FULL_IMAGE}
        '''
      }
    }

    stage('Health check') {
      steps {
        echo "Polling /health until service reports db OK (timeout 60s)"
        sh '''
          set -e
          TIMEOUT=60
          COUNT=0
          until curl -sS http://localhost:8000/health | grep -q '"db":"ok"'; do
            sleep 2
            COUNT=$((COUNT+2))
            echo "Waiting for healthy response... ${COUNT}s"
            if [ ${COUNT} -ge ${TIMEOUT} ]; then
              echo "Health check timed out"
              docker logs ${APP_CONTAINER} || true
              exit 1
            fi
          done
          echo "Service healthy"
        '''
      }
    }

    stage('Post-deploy test (optional)') {
      steps {
        echo "Run a simple post-deploy smoke test (insert/read)"
        sh '''
          # Create an employee (id returned)
          curl -s -X POST http://localhost:8000/employees -H "Content-Type: application/json" -d '{"name":"jenkins-test"}'
          # Try to read id 1 (optional; depends on DB state)
          # curl -s http://localhost:8000/employees/1
        '''
      }
    }
  }

  post {
    success {
      echo "Pipeline successful"
    }
    failure {
      echo "Pipeline failed — printing container logs for debugging"
      sh '''
        echo "=== APP LOGS ==="
        docker logs ${APP_CONTAINER} || true
        echo "=== DB LOGS ==="
        docker logs ${DB_CONTAINER} || true
      '''
    }
  }
}

