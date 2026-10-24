# Production Deployment Runbook

Owner: Platform Engineering. This runbook describes how services are released to production.

## Release Schedule

Production deployments happen on Tuesdays and Thursdays between 11:00 and 15:00 IST. There is a deployment freeze from Friday 14:00 until Monday 09:00. Emergency fixes during a freeze need approval from the on-call engineering manager.

## Pre-deployment Checklist

Before deploying, confirm that the CI pipeline is green, the pull request has at least 2 approvals, and a change ticket (prefix CHG-) exists in Jira describing the change and its rollback plan.

## Deployment Steps

Start the release with `deployctl release --service <name> --env prod`. The release first goes to a 10% canary for 30 minutes. If the canary is healthy, promote it with `deployctl promote --service <name>`.

## Rollback

Roll back immediately if the error rate exceeds 2% or p95 latency doubles during the canary. Use `deployctl rollback --service <name> --to <previous-tag>` and post in the #deployments channel.

## On-call

The primary on-call engineer must acknowledge a page within 15 minutes. If a page is not acknowledged within 30 minutes it escalates automatically to the secondary on-call engineer.
