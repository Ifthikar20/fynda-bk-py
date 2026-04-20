#!/bin/bash
# Check Celery logs on production
ssh -i ~/.ssh/outfi-api-key.pem ubuntu@54.81.148.134 "cd /home/ubuntu/outfi && docker compose -f docker-compose.prod.yml logs celery --tail=50"
