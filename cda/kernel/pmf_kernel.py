"""Compatibility shim: PMF symbol names mapped onto the EAK implementation.

The PMF (Process Management Framework) naming is superseded by EAK
(Embedded App Kernel), which shares the KernelCore base with OTK.
All existing PMF imports and usage continue to work unchanged.
"""

from cda.kernel import eak_kernel as _eak

# ── Re-export EAK symbols under their canonical names ────────────────────────
DEFAULT_HOST                   = _eak.DEFAULT_HOST
DEFAULT_PORT                   = _eak.DEFAULT_PORT
PLIST_LABEL                    = _eak.PLIST_LABEL
SERVICE_SPECS                  = _eak.SERVICE_SPECS
ServiceSpec                    = _eak.ServiceSpec
EAKKernel                      = _eak.EAKKernel
EAKKernelError                 = _eak.EAKKernelError

generate_plist                 = _eak.generate_plist
install_launchd                = _eak.install_launchd
uninstall_launchd              = _eak.uninstall_launchd
plist_path                     = _eak.plist_path
open_browser_when_ready        = _eak.open_browser_when_ready
wait_for_port_and_open_browser = _eak.wait_for_port_and_open_browser


# ── Backwards-compatible PMF aliases ─────────────────────────────────────────

class PMFKernelError(EAKKernelError):
    """Backwards-compatible PMF error alias over EAKKernelError."""


class PMFKernel(EAKKernel):
    """Backwards-compatible PMF class alias over EAKKernel."""
