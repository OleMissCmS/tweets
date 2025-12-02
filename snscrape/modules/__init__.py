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
			if hasattr(importer, 'find_spec'):
				spec = importer.find_spec(moduleName)
				if spec is not None and spec.loader is not None:
					module = importlib.util.module_from_spec(spec)
					spec.loader.exec_module(module)
				else:
					# Fallback to importlib.import_module
					module = __import__(moduleName, fromlist=[''])
			else:
				# Fallback for older importers
				module = __import__(moduleName, fromlist=[''])
		else:
			# Python < 3.12: use original find_module API
			module = importer.find_module(moduleName).load_module(moduleName)
		globals()[moduleNameWithoutPrefix] = module


_import_modules()
