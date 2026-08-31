#!/usr/bin/env bash
set -euo pipefail

# Bootstrap script for MCP Gateway learning project.
# Performs one-time cluster setup checks.

echo "=== MCP Gateway Bootstrap ==="

echo "Checking oc login..."
if ! oc whoami &>/dev/null; then
  echo "ERROR: Not logged into OpenShift. Run 'oc login' first."
  exit 1
fi

CLUSTER_DOMAIN=$(oc get ingress.config cluster -o jsonpath='{.spec.domain}')
echo "Cluster domain: ${CLUSTER_DOMAIN}"

echo "Checking cluster version..."
oc get clusterversion version -o jsonpath='{.status.desired.version}'
echo ""

echo "Checking if Connectivity Link operator is available in catalog..."
oc get packagemanifest rhcl-operator -n openshift-marketplace &>/dev/null \
  && echo "rhcl-operator: available" \
  || echo "WARNING: rhcl-operator not found in marketplace"

echo ""
echo "=== Bootstrap complete ==="
echo "Next: make deploy-operators"
