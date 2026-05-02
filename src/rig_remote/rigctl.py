"""
Compatibility shim — re-exports GQRXRigCtl as RigCtl.

Existing call sites that use ``from rig_remote.rigctl import RigCtl`` continue
to work without changes.  New code should import GQRXRigCtl directly from
``rig_remote.rig_backends.gqrx_rigctl``.
"""

from rig_remote.rig_backends.gqrx_rigctl import GQRXRigCtl as RigCtl

__all__ = ["RigCtl"]
