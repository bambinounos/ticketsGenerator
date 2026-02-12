Scripts creados
scripts/bump_version.sh - Bump de versiones

# Bump patch para ambos (ej: 1.1.0 -> 1.1.1)
./scripts/bump_version.sh all patch

# Bump minor solo servidor (ej: 1.1.0 -> 1.2.0)
./scripts/bump_version.sh server minor

# Bump major solo modulo Dolibarr (ej: 1.1.0 -> 2.0.0)
./scripts/bump_version.sh module major

Parametro	Opciones	Descripcion
component	server, module, all	Que componente actualizar
part	major, minor, patch	Que parte del semver incrementar


# 1. Bump version
./scripts/bump_version.sh all minor

# 2. Revisar cambios
git diff

# 3. Commit
git add -A && git commit -m "Bump version to X.Y.Z"

# 4. Generar zip del modulo para Dolibarr
./scripts/build_dolibarr_module.sh

# 5. Subir dist/module_raffles-X.Y.Z.zip a Dolibarr
