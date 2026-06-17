#!/usr/bin/env sh
set -eu

if [ "$#" -lt 1 ]; then
  echo "usage: scripts/release.sh VERSION [--push] [--docker]"
  exit 1
fi

VERSION="$1"
PUSH_GIT=0
PUSH_DOCKER=0

shift
for arg in "$@"; do
  case "$arg" in
    --push) PUSH_GIT=1 ;;
    --docker) PUSH_DOCKER=1 ;;
    *)
      echo "unknown argument: $arg"
      exit 1
      ;;
  esac
done

case "$VERSION" in
  [0-9]*.[0-9]*.[0-9]*) ;;
  *)
    echo "version must look like X.Y.Z"
    exit 1
    ;;
esac

if [ -n "$(git status --short)" ]; then
  echo "working tree must be clean before release"
  exit 1
fi

python3 scripts/set_version.py "$VERSION"

python3 -m py_compile media_downloader.py module/web.py module/app.py module/download_stat.py module/config_schema.py module/task_history.py
docker compose config >/dev/null
git diff --check

git add README.md README_CN.md docker-compose.yaml utils/__init__.py
git commit -m "release: ${VERSION}"
git tag "v${VERSION}"

if [ "$PUSH_GIT" -eq 1 ]; then
  git push origin master
  git push origin "v${VERSION}"
fi

if [ "$PUSH_DOCKER" -eq 1 ]; then
  docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -t "docker.io/roninriddle/telegram_media_downloader:${VERSION}" \
    -t "docker.io/roninriddle/telegram_media_downloader:latest" \
    --push .
fi
