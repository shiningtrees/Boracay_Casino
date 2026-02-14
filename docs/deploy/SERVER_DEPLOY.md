# Server Deploy (Docker + systemd)

서버에서 Boracay Casino를 도커 서비스로 올리는 빠른 방법입니다.

## One-clip install

서버에서 아래 한 줄 실행:

```bash
bash deploy/install_server.sh <REPO_URL> /opt/boracay-casino main
```

예시:

```bash
bash deploy/install_server.sh https://github.com/you/Boracay_Casino.git /opt/boracay-casino main
```

## After install

1) `.env` 값 입력

```bash
nano /opt/boracay-casino/.env
```

2) 서비스 재시작

```bash
sudo systemctl restart boracay-casino
```

3) 로그 확인

```bash
docker compose -f /opt/boracay-casino/docker-compose.yml logs -f --tail=200 casino
```

## Common operations

```bash
# 상태
sudo systemctl status boracay-casino

# 중지
sudo systemctl stop boracay-casino

# 시작
sudo systemctl start boracay-casino

# 업데이트
cd /opt/boracay-casino
git pull
sudo systemctl restart boracay-casino
```
