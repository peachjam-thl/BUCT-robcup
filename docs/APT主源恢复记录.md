# APT主源恢复准备与记录

日期：2026-11-18。**工具已在板端恢复主源；Ubuntu、ROS、RDK索引已拉取，无可见错误。系统已有ntp且曾同步成功，未安装timesyncd、未升级systemd；重启后RTC保持未通过。主源异常来源未定。**

## 已知事实

- Ubuntu 22.04.5 LTS / jammy，dpkg架构arm64。
- apt-get update与模拟安装在解析/etc/apt/sources.list第1行失败。主文件为root所有的普通文件、416字节、1个硬链接，内容含C++符号及NUL字节；原因未定。
- sources.list.d内ros-fish.list（78字节）指向清华ROS2 jammy arm64，sunrise.list（103字节）指向RDK X5 jammy仓库并指定sunrise.gpg。文本格式正常，不等于已验证服务器和签名可用。
- 没有查到主文件备份；修复前保留异常原文件和附加源目录。不因这个文件异常就认定整张卡已损坏，后续若重复损坏或出现I/O错误再进一步排查存储。

## 工具与使用

[restore_apt_sources.sh](../tools/restore_apt_sources.sh)固定用于本车已确认的jammy/arm64。默认--check只读；--apply需sudo，先建立唯一的/etc/apt/sources-backup-日期-随机后缀目录，备份主文件及sources.list.d，再在同目录暂存并替换主文件。平台、文件类型或Ubuntu公钥环检查失败时终止。

主源为jammy和jammy-updates的HTTPS清华Ubuntu Ports、jammy-security的HTTPS官方Ubuntu Ports。仅使用已有Ubuntu归档公钥环；不启用proposed、不添加其他发行版、不改ROS/RDK源或密钥、不自动更新/安装/升级软件。

Windows上传：

```powershell
scp "D:\Personal\Desktop\LETSROS\tools\restore_apt_sources.sh" wheeltec@192.168.128.10:/tmp/
```

小车SSH（ROS运动测试已结束、轮子静止）：

```bash
sudo bash /tmp/restore_apt_sources.sh --apply
```

只有出现RESTORED才继续：

```bash
sudo apt-get update
```

报错先保留输出，不忽略签名、证书或存储错误。本次更新后曾模拟systemd-timesyncd安装，发现会删除现有ntp并升级4个systemd相关包，因此未执行安装，转为检查已有ntp。当前不需要照此重做模拟或安装。

恢复时打印的BACKUP路径需记入日志。若需回退，先检查该备份文件与当前源，再制定恢复动作，不盲目覆盖。文件替换成功不等于APT所有源均可用，也不能解释异常来源。

## 本次实机结果

- BACKUP=/etc/apt/sources-backup-20261118-162833-2dzxK4；工具输出RESTORED。
- 备份sources.list的SHA256为58dc438db296a73c9485a260cc128af7989d9bacd7a3fb8a0f72efff42011f7d。
- 后续apt-get update已从Ubuntu jammy/updates/security、ROS2与RDK源拉取索引，输出31.9MB/43s，无可见错误；最后退出码未单独采集。
- 后续模拟安装可正常读取索引，但拟删除ntp、升级libpam-systemd/libsystemd0/systemd/systemd-sysv；未实际安装或升级。
- 已有ntp.service active/enabled，16:43同步标志yes、ntpq leap_none/sync_ntp、RTC读值正确；未改ntp.conf或手动写RTC。重启后16:55系统日期正确但RTC回2000、同步标志no，保持未通过。
- 重启后USB地址可ping但SSH曾拒绝，随后电脑TCP22恢复响应；具体根因及恢复操作未确认。已暂停进一步时间维护，先接续静态雷达。完整过程见[当日日志](../日志/2026-11-18.md)。恢复APT源不等于整机恢复或RTC保持通过。

核对资料：[APT jammy源格式](https://manpages.ubuntu.com/manpages/jammy/man5/sources.list.5.html)、[Ubuntu Ports jammy元数据](https://ports.ubuntu.com/ubuntu-ports/dists/jammy/Release)、[清华Ubuntu Ports说明](https://mirrors.tuna.tsinghua.edu.cn/help/ubuntu-ports/)。清华页面默认发行版可能变化，本工具固定jammy，不复制页面当前默认代号。
