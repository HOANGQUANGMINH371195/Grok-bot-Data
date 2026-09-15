console.error('BLOCKED infra-validate: approved deployment bindings (domain, budget, operators, OIDC role and secret references) are not configured; no Terraform apply is performed.');
process.exitCode = 2;
