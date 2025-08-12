import argparse
import os
import sys
import subprocess
import shutil

# --- 設定 ---
NODE_EXPORTER_VERSION = "1.9.1"
REMOTE_BINARY_PATH = "/usr/local/bin/node_exporter"
SYSTEMD_SERVICE_FILE = "/etc/systemd/system/node_exporter.service"

SYSTEMD_TEMPLATE = f"""
[Unit]
Description=Node Exporter
Wants=network-online.target
After=network-online.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart={REMOTE_BINARY_PATH}

[Install]
WantedBy=multi-user.target
"""

def run_local_command(command_list):
    """在本機上執行一個指令並印出輸出"""
    print(f"--- 執行中: {' '.join(command_list)} ---")
    try:
        # 使用 subprocess.run 來執行指令
        # check=True 會在指令回傳非 0 退出碼時拋出例外
        result = subprocess.run(command_list, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        return True
    except FileNotFoundError:
        print(f"錯誤: 找不到指令 '{command_list[0]}'. 請確認該工具已安裝。", file=sys.stderr)
        return False
    except subprocess.CalledProcessError as e:
        print(f"!!! 指令 '{' '.join(command_list)}' 執行失敗 !!!", file=sys.stderr)
        print(f"退出碼: {e.returncode}", file=sys.stderr)
        print(f"標準輸出:\n{e.stdout}", file=sys.stderr)
        print(f"標準錯誤:\n{e.stderr}", file=sys.stderr)
        return False

def main():
    # 檢查是否以 root/sudo 權限執行
    if os.geteuid() != 0:
        print("錯誤: 這個腳本需要以 root 或 sudo 權限執行。", file=sys.stderr)
        print("請嘗試使用: sudo python3 your_script_name.py ...", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="在本機上自動部署 Node Exporter。請使用 sudo 執行。")
    
    # 部署模式選擇
    parser.add_argument("--deploy-method", choices=['download', 'upload'], default='download', 
                        help="部署模式：'download' (從 GitHub 下載) 或 'upload' (從本地路徑複製)。預設為 'download'。")
    parser.add_argument("--version", default=NODE_EXPORTER_VERSION, 
                        help=f"若使用 'download' 模式，要下載的 node_exporter 版本。預設為 {NODE_EXPORTER_VERSION}。")
    parser.add_argument("--binary-path", default="./node_exporter",
                        help="若使用 'upload' 模式，指定 node_exporter 執行檔的來源路徑。預設為 './node_exporter'。")
    
    args = parser.parse_args()

    # --- 開始部署 ---
    try:
        # 1. 建立專用使用者
        print("\n[步驟 1/5] 建立 node_exporter 專用使用者...")
        # || true 可以在 useradd 因為使用者已存在而失敗時，不中斷整個腳本
        run_local_command(["useradd", "--no-create-home", "--shell", "/bin/false", "node_exporter"]) or print("使用者可能已存在，繼續。")

        # 2. 部署執行檔
        print(f"\n[步驟 2/5] 部署 node_exporter 執行檔 (模式: {args.deploy_method})...")
        if args.deploy_method == 'download':
            arch = "amd64"
            tarball_name = f"node_exporter-{args.version}.linux-{arch}.tar.gz"
            dir_name = f"node_exporter-{args.version}.linux-{arch}"
            download_url = f"https://github.com/prometheus/node_exporter/releases/download/v{args.version}/{tarball_name}"
            
            print(f"正在下載: {download_url}")
            run_local_command(["curl", "-LO", download_url])
            run_local_command(["tar", "-xvf", tarball_name])
            
            # 使用 shutil 來複製檔案，更具可移植性
            source_file = os.path.join(dir_name, "node_exporter")
            shutil.copy(source_file, REMOTE_BINARY_PATH)
            print(f"已將 {source_file} 複製到 {REMOTE_BINARY_PATH}")
            
            shutil.rmtree(dir_name)
            os.remove(tarball_name)
            print("已清除暫存檔案。")
        else: # upload 模式
            if not os.path.exists(args.binary_path):
                print(f"錯誤: 找不到指定的檔案 '{args.binary_path}'。", file=sys.stderr)
                sys.exit(1)
            print(f"從 '{args.binary_path}' 複製檔案...")
            shutil.copy(args.binary_path, REMOTE_BINARY_PATH)
            print(f"已將 {args.binary_path} 複製到 {REMOTE_BINARY_PATH}")

        run_local_command(["chown", "node_exporter:node_exporter", REMOTE_BINARY_PATH])
        run_local_command(["chmod", "755", REMOTE_BINARY_PATH])

        # 3. 建立 systemd 服務檔案
        print("\n[步驟 3/5] 建立 systemd 服務檔案...")
        with open(SYSTEMD_SERVICE_FILE, "w") as f:
            f.write(SYSTEMD_TEMPLATE)
        print(f"已成功寫入設定到 {SYSTEMD_SERVICE_FILE}")

        # 4. 啟動並啟用服務
        print("\n[步驟 4/5] 啟動並啟用 node_exporter 服務...")
        run_local_command(["systemctl", "daemon-reload"])
        run_local_command(["systemctl", "start", "node_exporter"])
        run_local_command(["systemctl", "enable", "node_exporter"])

        # 5. 驗證服務狀態
        print("\n[步驟 5/5] 驗證服務狀態...")
        run_local_command(["systemctl", "status", "node_exporter"])
        run_local_command(["ss", "-tlpn"]) # 不再 grep, 直接顯示所有監聽中的 port 方便確認

        print("\n🎉 部署成功！")

    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()