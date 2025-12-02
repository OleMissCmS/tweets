import pkgutil
import sys
import importlib.util


__all__ = []


def _import_modules():
	prefixLen = len(__name__) + 1
	for importer, moduleName, isPkg in pkgutil.iter_modules(__path__, prefix = f'{__name__}.'):
		assert not isPkg
		moduleNameWithoutPrefix = moduleName[prefixLen:]
		__all__.append(moduleNameWithoutPrefix)
		# Python 3.12+ compatibility: use modern importlib API
		if sys.version_info >= (3, 12):
			# Use importlib.import_module which handles everything correctly
			module = __import__(moduleName, fromlist=[''])
			# Ensure __module__ is set correctly for dataclasses
			if not hasattr(module, '__module__') or module.__module__ is None:
				module.__module__ = moduleName
		else:
			# Python < 3.12: use original find_module API
			module = importer.find_module(moduleName).load_module(moduleName)
		globals()[moduleNameWithoutPrefix] = module


_import_modules()
