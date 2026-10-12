# WujiaTea ERP — Thông tin kết nối

Cập nhật 12/10/2026: chuyển sang hạ tầng mới (repo, máy UAT, aaPanel, Metabase). Việc đổi repo + mô hình nhánh:
`docs/next-session-repo-migration.md`.

## GitHub
| | |
|---|---|
| Repo | https://github.com/huynhngoanhthai/WujiaTea-ERP-internal.git |
| Repo cũ | https://github.com/huyban2003/WujiaTea-ERP-internal (ngừng dùng sau khi phiên repo chuyển xong) |
| Token | (xem trong password manager — không lưu ở đây) |

## UAT (dev server) — từ 12/10/2026
| | |
|---|---|
| URL | https://dev.wujiatea.com.vn (Discuss: `/odoo/discuss`, portal: `/portal`) |
| IP | `115.74.247.189` (nginx đứng trước Odoo) |
| Database | `wujia_tea_19` (cùng máy còn `wujia_mn`, `huipeng_db`) |
| Đăng nhập | `admin` / `Wujia@2026` (kiểm đăng nhập được 12/10/2026, quyền hệ thống) |

## aaPanel — quản lý máy chủ
| | |
|---|---|
| URL | https://aapanel.hongtrangogia.com/4b9b3f91 |
| Username | `wujia` |
| Password | `admin` |

Đăng nhập phải qua trình duyệt (request thường trả 404). Đường dẫn trên máy:

| | |
|---|---|
| Source UAT | `/www/wwwroot/dev.wujiatea.com.vn` (nhánh `deploy/staging`) |
| Service | `odoo-dev` (systemd, user `www`, cổng 8019) |
| Config Odoo | `/www/wwwroot/dev.wujiatea.com.vn/config/odoo.conf` (ngoài git; `addons_path` ở đây) |
| Deploy | Website → `dev.wujiatea.com.vn` → Conf → Git Manager → *Deploy latest* (không tự deploy khi merge) ⇒ git hook ở `/www/server/git_hooks/dev.wujiatea.com.vn/` gọi `/www/wwwroot/dev.wujiatea.com.vn/deploy.sh` (ngoài git; dòng 222 dò module) |
| Log | `/www/wwwroot/dev.wujiatea.com.vn/logs/<năm>/<tháng>/<năm-tháng-ngày>.log` (giờ UTC) · `journalctl -u odoo-dev` |
| Sao lưu trước ADR-028 | `config/odoo.conf.bak-adr028` · `deploy.sh.bak-adr028` |

## Metabase
| | |
|---|---|
| URL | https://metabase.hongtrangogia.com |
| Username | `admin@wujia.com` |
| Password | `Admin@123` |

## Máy cũ (ngừng dùng từ 12/10/2026)

### Server Windows
| | |
|---|---|
| IP WAN | `113.161.187.126` |
| RDP Port | `5761` |
| Username | `dev` |
| Password | `Dev@2026` |

### Odoo
| | |
|---|---|
| HTTP Port | `8019` |
| Longpolling Port | `8020` |
| Database | `wujia_tea_19` |
| DB User | `odoo19` |
| DB Password | `1` |
| Admin Password | `wujia_admin` |
