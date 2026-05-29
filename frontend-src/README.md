# Frontend Source Notes

当前线上仍直接加载 `public/app.js` 和 `public/styles.css`，这样服务器不需要 Node 构建环境。

这个目录用于后续逐步迁移到 TypeScript：

- 保持现有业务逻辑不变，先抽类型和纯函数。
- 迁移完成后再引入明确的构建命令，把输出写回 `public/app.js`。
- 不在服务器上直接构建；仍按约定先本地修改和测试，再上传服务器。

本次只新增 TS 配置骨架，不改变运行链路。
