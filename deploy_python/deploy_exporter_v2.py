  #!/usr/bin/env python3
import argparse
import os
import sys
import subprocess
import shutil
import tempfile

# --- 全域設定 ---
NODE_EXPORTER_VERSION = "1.9.1"
INSTALL_PATH = "/usr/local/bin/node_exporter"
SERVICE_USER = "node_exporter"
SERVICE_FILE_PATH = f"/etc/systemd/system/{SERVICE_USER}.service"
NODE_EXPORTER_PORT = "9100"

# systemd 服務檔案的內容範本
SYSTEMD_TEMPLATE = f"""
[Unit]
Description=Node Exporter
Wants=network-online.target
After=network-online.target

[Service]
User={SERVICE_USER}
Group={SERVICE_USER}
Type=simple
ExecStart={INSTALL_PATH}

[Install]
WantedBy=multi-user.target
"""

def run_command(command_list, check=True, input_data=None):
    """在本機上執行一個指令，並處理輸出和錯誤"""
    command_str = ' '.join(command_list)
    print(f"--- 執行中: {command_str} ---")
    try:
        # 將 input_data 傳遞給 subprocess.run
        result = subprocess.run(command_list, check=check, capture_output=True, text=True, encoding='utf-8', input=input_data)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return True
    except FileNotFoundError:
        print(f"錯誤: 找不到指令 '{command_list[0]}'. 請確認該工具已安裝。", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"!!! 指令 '{command_str}' 執行失敗 !!!", file=sys.stderr)
        if e.stdout:
            print(f"標準輸出:\n{e.stdout}", file=sys.stderr)
        if e.stderr:
            print(f"標準錯誤:\n{e.stderr}", file=sys.stderr)
        if check:
             sys.exit(1)
        return False
    except KeyboardInterrupt:
        print("\n使用者中斷操作。")
        sys.exit(1)

def setup_user():
    """建立專用的系統使用者"""
    print("\n[步驟 1/6] 建立 node_exporter 專用使用者...")
    try:
        subprocess.run(["id", SERVICE_USER], check=True, capture_output=True)
        print(f"使用者 '{SERVICE_USER}' 已存在，略過。")
    except subprocess.CalledProcessError:
        print(f"使用者 '{SERVICE_USER}' 不存在，正在建立...")
        run_command(["useradd", "--no-create-home", "--shell", "/bin/false", SERVICE_USER])

def deploy_binary_from_download(version):
    """從 GitHub 下載、解壓縮並安裝 node_exporter"""
    arch = "amd64"
    tarball_name = f"node_exporter-{version}.linux-{arch}.tar.gz"
    dir_name = f"node_exporter-{version}.linux-{arch}"
    download_url = f"https://github.com/prometheus/node_exporter/releases/download/v{version}/{tarball_name}"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"進入臨時目錄: {tmpdir}")
        original_dir = os.getcwd()
        os.chdir(tmpdir)
        print(f"正在下載: {download_url}")
        run_command(["curl", "-sLO", download_url])
        print("解壓縮中...")
        run_command(["tar", "-xzf", tarball_name])
        source_file = os.path.join(dir_name, "node_exporter")
        print(f"安裝執行檔到 {INSTALL_PATH}...")
        run_command(["mv", source_file, INSTALL_PATH])
        os.chdir(original_dir)
    print("已清除暫存檔案。")

def deploy_binary_from_local(binary_path):
    """從本地路徑複製 node_exporter"""
    if not os.path.exists(binary_path):
        print(f"錯誤: 找不到指定的檔案 '{binary_path}'。", file=sys.stderr)
        sys.exit(1)
    print(f"從 '{binary_path}' 複製檔案到 {INSTALL_PATH}...")
    try:
        shutil.copy(binary_path, INSTALL_PATH)
    except Exception as e:
        print(f"複製檔案時發生錯誤: {e}", file=sys.stderr)
        sys.exit(1)

def setup_permissions():
    """設定執行檔的權限和所有權"""
    print("設定檔案權限...")
    run_command(["chown", f"{SERVICE_USER}:{SERVICE_USER}", INSTALL_PATH])
    run_command(["chmod", "755", INSTALL_PATH])

def setup_systemd_service():
    """建立並寫入 systemd 服務檔案"""
    print("\n[步驟 3/6] 建立 systemd 服務檔案...")
    try:
        with open(SERVICE_FILE_PATH, "w") as f:
            f.write(SYSTEMD_TEMPLATE)
        print(f"已成功寫入設定到 {SERVICE_FILE_PATH}")
    except IOError as e:
        print(f"寫入 systemd 服務檔案時發生錯誤: {e}", file=sys.stderr)
        sys.exit(1)

def start_and_enable_service():
    """啟動並啟用 systemd 服務"""
    print("\n[步驟 4/6] 啟動並啟用 node_exporter 服務...")
    run_command(["systemctl", "daemon-reload"])
    run_command(["systemctl", "start", SERVICE_USER])
    run_command(["systemctl", "enable", SERVICE_USER])

def configure_firewall(allowed_ip):
    """自動偵測並設定防火牆規則"""
    print(f"\n[步驟 5/6] 設定防火牆，允許來自 {allowed_ip} 的連線...")
    
    if shutil.which("ufw"):
        print("偵測到 ufw，正在設定規則...")
        run_command(["ufw", "allow", "from", allowed_ip, "to", "any", "port", NODE_EXPORTER_PORT, "proto", "tcp"])
        # 在執行 ufw enable 時，自動輸入 'y'
        run_command(["ufw", "enable"], check=False, input_data="y\n")
        run_command(["ufw", "status"])
    elif shutil.which("firewall-cmd"):
        print("偵測到 firewalld，正在設定規則...")
        rule = f'rule family="ipv4" source address="{allowed_ip}" port port="{NODE_EXPORTER_PORT}" protocol="tcp" accept'
        run_command(["firewall-cmd", "--permanent", "--add-rich-rule", rule])
        run_command(["firewall-cmd", "--reload"])
        run_command(["firewall-cmd", "--list-rich-rules"])
    else:
        print("警告: 在系統中找不到 ufw 或 firewalld。請手動設定您的防火牆，開放 TCP port 9100。")

def verify_installation():
    """驗證安裝結果"""
    print("\n[步驟 6/6] 驗證服務狀態...")
    run_command(["systemctl", "status", SERVICE_USER], check=False)
    print("\n檢查 Port 9100 是否正在監聽...")
    run_command(["ss", "-tlpn"], check=False)

def main():
    if os.geteuid() != 0:
        print("錯誤: 這個腳本需要以 root 或 sudo 權限執行。", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="在本機上自動部署 Node Exporter 並設定防火牆。請務必使用 sudo 執行。")
    
    parser.add_argument("--deploy-method", choices=['download', 'upload'], default='download', 
                        help="部署模式：'download' (從 GitHub 下載) 或 'upload' (從本地路徑複製)。")
    parser.add_argument("--version", default=NODE_EXPORTER_VERSION, 
                        help=f"若使用 'download' 模式，要下載的 node_exporter 版本。")
    parser.add_argument("--binary-path", default="./node_exporter",
                        help="若使用 'upload' 模式，指定 node_exporter 執行檔的來源路徑。")
    parser.add_argument("--allow-ip", help="指定允許存取 9100 port 的來源 IP 位址 (例如 Prometheus 主機 IP)。如果提供此參數，將會自動設定防火牆。")
    
    args = parser.parse_args()

    setup_user()
    
    print(f"\n[步驟 2/6] 部署 node_exporter 執行檔 (模式: {args.deploy_method})...")
    if args.deploy_method == 'download':
        deploy_binary_from_download(args.version)
    else:
        deploy_binary_from_local(args.binary_path)
    
    setup_permissions()
    setup_systemd_service()
    start_and_enable_service()

    # 如果使用者提供了 --allow-ip 參數，就執行防火牆設定
    if args.allow_ip:
        configure_firewall(args.allow_ip)

    verify_installation()

    print("\n🎉 部署成功！")

if __name__ == "__main__":
    main()

"""執行command請參考以下"""
"""sudo python3 deploy_exporter_v2.py --version 1.9.1 --allow-ip 10.239.35.3"""