import subprocess
import sys

# --- 您可以修改這裡的設定 ---
IMAGE_NAME = "nvcr.io/nvidia/k8s/dcgm-exporter:4.2.3-4.1.3-ubuntu22.04"
CONTAINER_NAME = "dcgm-exporter"
# -----------------------------

def run_command(command, check_error=True, quiet=False):
    """執行一個系統指令並處理輸出和錯誤"""
    print(f"🚀 Executing: {' '.join(command)}")
    try:
        # 使用 subprocess.run 來執行指令
        # capture_output=True 會捕捉標準輸出和錯誤
        # text=True 讓輸出以文字形式呈現
        result = subprocess.run(
            command, 
            capture_output=True, 
            text=True, 
            check=check_error # 如果指令返回非零碼 (錯誤)，則會拋出例外
        )
        if not quiet and result.stdout:
            print(f"✅ Output:\n---\n{result.stdout.strip()}\n---")
        return result.stdout.strip()
    except FileNotFoundError:
        print(f"❌ Error: Command '{command[0]}' not found. Is it installed and in your PATH?")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed with exit code {e.returncode}:")
        print(f"   Command: {' '.join(e.cmd)}")
        if e.stdout:
            print(f"   stdout:\n{e.stdout.strip()}")
        if e.stderr:
            print(f"   stderr:\n{e.stderr.strip()}")
        # 對於 stop/rm 的 "No such container" 錯誤，我們將其視為成功
        if "No such container" in e.stderr:
            print("   (Ignoring 'No such container' error, this is expected if container was not running.)")
        else:
            sys.exit(1) # 其他錯誤則終止腳本


def main():
    """主執行函式"""
    print("===== DCGM Exporter Deployment Script =====")
    
    # 步驟 0: 預先請求一次 sudo 權限，利用系統快取
    print("\n[Step 0] Caching sudo credentials...")
    print("The script will now ask for your password to run sudo commands.")
    print("You will only need to enter it once.")
    run_command(["sudo", "-v"], quiet=True) # -v 會更新 sudo 的時間戳，如果需要會提示輸入密碼
    print("✅ Sudo credentials cached.")

    # 步驟 1: 清理舊的容器
    print(f"\n[Step 1] Cleaning up old container named '{CONTAINER_NAME}'...")
    # 這裡我們不檢查錯誤，因為容器不存在是正常情況
    run_command(["sudo", "docker", "stop", CONTAINER_NAME], check_error=False)
    run_command(["sudo", "docker", "rm", CONTAINER_NAME], check_error=False)
    print("✅ Cleanup complete.")

    # 步驟 2: 下載指定版本的 Docker Image
    print(f"\n[Step 2] Pulling new Docker image: {IMAGE_NAME}...")
    run_command(["sudo", "docker", "pull", IMAGE_NAME])
    print("✅ Image pulled successfully.")

    # 步驟 3: 運行新的 Docker 容器 (持久化版本)
    print(f"\n[Step 3] Running new persistent container '{CONTAINER_NAME}'...")
    run_command([
        "sudo", "docker", "run",
        # "--rm", # <-- 我們拿掉了這一行，讓容器可以持久存在
        "-d",
        "--restart", "unless-stopped", # <-- 我們加入了這一行，設定自動重啟策略
        "--gpus", "all",
        "-p", "9400:9400",
        "--name", CONTAINER_NAME,
        IMAGE_NAME
    ])
    print("✅ Persistent container started successfully.")

    # 步驟 4: 驗證容器運行狀態
    print("\n[Step 4] Verifying container status...")
    run_command(["sudo", "docker", "ps"])
    print("✅ Container status checked.")

    # 步驟 5: 按下 Enter 後進行最終確認
    print("\n[Step 5] Final verification...")
    try:
        input("Press Enter to run the final curl check...")
    except KeyboardInterrupt:
        print("\nAborted by user.")
        sys.exit(1)
        
    run_command(["curl", "http://localhost:9400/metrics"])
    print("\n===== 🎉 Deployment Complete! =====")


if __name__ == "__main__":
    main()