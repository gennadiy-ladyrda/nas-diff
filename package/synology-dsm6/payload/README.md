# Payload

Этот каталог соответствует содержимому будущего `package.tgz`.

Все файлы из `payload/` должны устанавливаться как immutable package assets в package target directory.

Persistent data сюда не помещаются.

Для package build flow:
- `payload/images/` содержит bundled image archives для offline install
- `payload/runtime/` содержит compose/env/scripts для package runtime
- `payload/ui/` содержит DSM launcher assets
