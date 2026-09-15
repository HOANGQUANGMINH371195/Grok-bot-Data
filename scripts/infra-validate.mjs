console.error('BLOCKED infra-validate: approved AWS account, region, domain, budget and deployment bindings are not configured; no Terraform apply is performed.');
process.exitCode = 2;
