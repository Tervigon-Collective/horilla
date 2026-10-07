// Horilla HRMS: checks + deploy on push to main.
//
// The live checkout (/srv/seleric/hrms/horilla) is a git clone that people
// also edit in place, so the deploy never copies files over it (the old
// rsync --delete job could wipe live work). It fast-forwards the checkout to
// the pushed commit -- git refuses rather than overwrite uncommitted edits --
// then applies what changed: image rebuild only for Dockerfile/requirements,
// migrate for new migrations, collectstatic for static files, otherwise a
// graceful gunicorn reload (no downtime) and a restart of the scheduler and
// the biometric receiver.
//
// Jenkins job: "Pipeline script from SCM", repo Tervigon-Collective/horilla,
// branch */main, script path Jenkinsfile. The jenkins user writes the
// checkout through the tervigon group (tree is g+w, dirs setgid).
pipeline {
    agent any
    options {
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
    }
    triggers { githubPush() }
    environment {
        APP_DIR = '/srv/seleric/hrms/horilla'
        COMPOSE = 'docker compose -f docker-compose.server.yml -f ../docker-compose.seleric.prod.yaml'
        HEALTH_URL = 'http://127.0.0.1:18083/'
        GIT_LIVE = 'git -c safe.directory=/srv/seleric/hrms/horilla -C /srv/seleric/hrms/horilla'
    }
    stages {
        stage('Checks') {
            steps {
                sh '''
                    set -eu
                    echo "== Python syntax (every module)"
                    python3 -m compileall -q -x '(^|/)(\\.git|\\.venv|node_modules|staticfiles|media)/' . >/dev/null \
                      || { python3 -m compileall -q -x '(^|/)(\\.git|\\.venv|node_modules|staticfiles|media)/' . ; exit 1; }
                    echo "== Django system check on the pushed code (current image, throwaway container)"
                    docker run --rm --network horilla_default --env-file "$APP_DIR/.env" \
                      -e HORILLA_SKIP_RELEASE_TASKS=1 -e PYTHONDONTWRITEBYTECODE=1 \
                      -v "$WORKSPACE:/app" -w /app --entrypoint python \
                      horilla-web:latest manage.py check
                '''
            }
        }
        stage('Deploy') {
            steps {
                sh '''
                    set -eu
                    umask 0002   # files git writes stay editable by the tervigon group
                    NEW=$(git rev-parse HEAD)
                    BRANCH=$($GIT_LIVE rev-parse --abbrev-ref HEAD)
                    [ "$BRANCH" = main ] || { echo "FAIL: live checkout is on '$BRANCH', not main"; exit 1; }
                    OLD=$($GIT_LIVE rev-parse HEAD)
                    $GIT_LIVE fetch --quiet "$WORKSPACE" HEAD
                    if [ "$OLD" = "$NEW" ] || $GIT_LIVE merge-base --is-ancestor "$NEW" "$OLD"; then
                        echo "Live checkout already has $NEW (it was pushed from there)."
                    elif $GIT_LIVE merge-base --is-ancestor "$OLD" "$NEW"; then
                        echo "Fast-forward live checkout $OLD -> $NEW"
                        $GIT_LIVE merge --ff-only --quiet FETCH_HEAD || {
                            echo "FAIL: fast-forward refused -- uncommitted edits in the live checkout touch the same files."
                            $GIT_LIVE status --short | head -30
                            exit 1
                        }
                    else
                        echo "FAIL: live checkout ($OLD) and pushed main ($NEW) have diverged; merge them in the live checkout."
                        exit 1
                    fi

                    CHANGED=$($GIT_LIVE diff --name-only "$OLD" HEAD || true)
                    echo "$CHANGED" | sed -n '1,40p'
                    cd "$APP_DIR"
                    if echo "$CHANGED" | grep -qE '^(Dockerfile|requirements[^/]*\\.txt|docker-compose\\.server\\.yml|entrypoint[^/]*)$'; then
                        echo "== Image inputs changed: rebuild and recreate"
                        $COMPOSE build web
                        $COMPOSE up -d web scheduler biometric-push
                    else
                        if echo "$CHANGED" | grep -q '/migrations/'; then
                            echo "== migrate"
                            docker exec horilla-web-1 python manage.py migrate --noinput
                        fi
                        if echo "$CHANGED" | grep -qE '(^|/)static/'; then
                            echo "== collectstatic"
                            docker exec horilla-web-1 python manage.py collectstatic --noinput >/dev/null
                        fi
                        echo "== graceful reload (gunicorn HUP) + restart background services"
                        docker exec horilla-web-1 sh -c 'kill -HUP 1'
                        docker restart horilla-scheduler-1 horilla-biometric-push-1 >/dev/null
                    fi
                '''
            }
        }
        stage('Health check') {
            steps {
                sh '''
                    set -eu
                    for i in $(seq 1 40); do
                      CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$HEALTH_URL" 2>/dev/null || true)
                      case "${CODE:-000}" in
                        200|301|302) echo "OK: HRMS HTTP $CODE"; exit 0 ;;
                      esac
                      echo "attempt $i: HTTP ${CODE:-000}"
                      sleep 3
                    done
                    exit 1
                '''
            }
        }
    }
    post {
        failure {
            sh 'docker logs --tail 80 horilla-web-1 2>&1 || true; docker ps --filter name=horilla || true'
        }
    }
}
