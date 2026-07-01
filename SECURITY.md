# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it by:

1. **Email**: Create an issue on GitHub (for non-critical issues)
2. **GitHub Security Advisory**: For critical vulnerabilities, use [GitHub's private vulnerability reporting](https://github.com/WHU_Clover/comsol-simulation-toolkit/security/advisories/new)

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if available)

## Security Considerations

### COMSOL Integration
- This toolkit executes COMSOL Java API calls via JPype
- Only run `.mph` models from trusted sources
- Be cautious with user-provided model paths and parameters

### Environment Variables
- `.env` files may contain sensitive paths
- Add `.env` to `.gitignore` (done by default)
- Do not commit credentials or API keys

### Dependencies
- Review `pyproject.toml` dependencies before installation
- We use standard scientific Python packages (numpy, pandas, JPype, mph)
- No external network requests by default

## Best Practices

1. **Validate Inputs**: Always validate paths and parameters from user input
2. **Isolate Environments**: Use virtual environments for project isolation
3. **Review Models**: Inspect `.mph` files before loading
4. **Keep Updated**: Regularly update dependencies for security patches

## Disclosure Policy

- We aim to respond to security reports within 48 hours
- Fixes will be released as patch versions
- Credit will be given to reporters (unless anonymity requested)

## Out of Scope

- Issues requiring physical access to the machine
- Denial of service via resource exhaustion (COMSOL simulations are resource-intensive by design)
- Vulnerabilities in COMSOL Multiphysics itself (report to COMSOL Inc.)
