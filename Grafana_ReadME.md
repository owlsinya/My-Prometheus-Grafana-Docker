### Grafana / Prometheus 設定 ReadME

<br>

此教學由 Grafana 與 Prometheus 後端連接起來後開始，說明在 Grafana 要設定新的自定義 Dashboard 時需要注意的項目
此專案版本：
Grafana:9.0.0
Prometheus:v2.35.0
(其餘版本設定請參考 docker-compose.yaml)

<br>

#### 1. 影響前端 Dashboard 的 Variable 變數

<br>

新增一個 Dashboard 之後，請找右上方的齒輪進入 settings
在左方選單中選擇 Variables，在此範例中，最終總共建立 job / node / instance / gpu 四個變數。
四個變數的名稱對應的即是在 Prometheus.yaml 中的 job_name / targets / alias / gpu - alias ，
名稱之間都是可以自行定義，沒有一定限制，但需要注意是否會混淆或衝突。


