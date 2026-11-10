# PositionBar Homebrew tap

安装已正式发布的 PositionBar：

```sh
brew install --cask positionbar/tap/positionbar
```

安装包、Sparkle 更新源、版本与 changelog 统一在 [PositionBar/releases](https://github.com/PositionBar/releases) 管理。只有该仓库中经过审批的发布 PR 合并后才会构建发布。本 tap 不再默认运行脚本回归，也不构建或发布 App。

`Casks/positionbar.rb` 只由真实、公开可下载且已验证的 Universal DMG 生成。首次发布前不会提交占位 cask 或虚构 SHA。macOS 最低版本来自实际包中声明，正式包必须包含 arm64 与 x86_64。

发布中心使用 `scripts/cask.py publish --receipt /absolute/homebrew.json --execute`：重新下载 GitHub Release 的精确 DMG，核对 SHA-256、长度、Apple Team / Bundle ID、Developer ID 签名、公证/staple、Gatekeeper、Sparkle 公钥与固定 feed，再写入 cask 和 `Releases/<tag>.json` 的验证记录。资产 URL 必须属于 `PositionBar/releases` 的同一 tag；不可把测试 fixture 当正式发行。

不加 `--execute` 仅显示 dry-run；不下载、不写文件、不提交或推送。发布中心提供独立的 `TAP_WRITE_TOKEN`，本仓库不再使用 Apple 或 Sparkle 私钥构建 App。原本保存的 Secrets 不会被自动迁移或删除。

commit/push 的不确定结果通过 origin/main 与已生成 cask/receipt 读回恢复；不覆盖不同源码或字节的发行记录，不强推。App 与 DMG、appcast 与 notes 的签名由发布中心验证，本 tap 复验包本身并保留这些事实。签名身份、Keychain service 与权限不因 Homebrew 分发改变。

只保留 cask 文本渲染的局部函数测试；仅修改该函数时按需执行 `PYTHONPATH=tests python3 -B -m unittest test_cask.RenderingTests -q`，完整本地测试共用 60 秒预算。日常不跑脚本回归、模拟签名或临时 Git 发布实验。正式发布时的真实 DMG 下载、签名、公证、SHA 校验与不可变记录保护继续保留。
