#!/bin/bash
# Check Celery logs on production
ssh -i ~/.ssh/fynda-api-key.pem ubuntu@54.81.148.134 "cd /home/ubuntu/fynda && docker compose -f docker-compose.prod.yml logs celery --tail=50"
