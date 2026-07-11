"""Mixin for extending betterproto2 generated message classes with extra methods."""

from __future__ import annotations

import sys

import betterproto2


class MonkeyPatcher:
    """Mixin that replaces the original generated class in its module on subclass creation.

    Subclass a betterproto2 generated message class together with ``MonkeyPatcher``
    to add extra methods.  The subclass automatically replaces the original class
    in its module so that all deserialization produces instances of the subclass.

    The parent's :class:`~betterproto2.ProtoClassMetadata` is inherited (not
    recomputed) because the generated type hints reference module-local imports
    (e.g. ``_common__.HelloReply``) that do not exist in the subclass's module
    namespace.

    The message pool entry is updated so ``Any.pack()`` / ``Any.unpack()``
    resolves to the patched class.

    Example::

        from greeter.greeter.common import HelloRequest
        from grpclib_transports.monkey_patcher import MonkeyPatcher

        class HelloRequestExt(HelloRequest, MonkeyPatcher):
            def formatted_name(self) -> str:
                return self.name.upper()
    """

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        for base in cls.__mro__[1:]:
            if not issubclass(base, betterproto2.Message) or issubclass(base, MonkeyPatcher):
                continue

            # Inherit the parent's proto metadata to avoid recomputing
            # type hints in the subclass's module (which lacks the
            # generated module's imports like ``_common__``).
            _ = base._betterproto  # pyright: ignore[reportPrivateUsage] -- need to force lazy metadata computation
            cls._betterproto_meta = base._betterproto_meta  # pyright: ignore[reportPrivateUsage] -- copy parent metadata to subclass

            # Replace the original class in its module so that all
            # deserialization produces instances of the subclass.
            original_module = sys.modules[base.__module__]
            setattr(original_module, base.__name__, cls)

            # Update the message pool so Any.pack()/Any.unpack()
            # resolves to the patched class.
            pool = getattr(original_module, "default_message_pool", None)
            if pool is not None and base in pool.type_to_url:
                url = pool.type_to_url[base]
                pool.url_to_type[url] = cls
                pool.type_to_url[cls] = url
                del pool.type_to_url[base]
            break
