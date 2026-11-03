#### 预测电价计算：
'''
P零售 = {linkagePrice=k_midterm*priceMonthAvgRealTime+k_spot*aRealTime+dp_float;
        k_fixed*p_fixed+k_float*linkagePrice}
P到户 = PurchaseAlg*floatFactor+outLineLossPrice+unitConveyPrice+sysOperateFeePrice+governmentAppendPrice+otherPrice
'''
import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(InsecureRequestWarning)
if __name__ == "__main__":
    import psycopg2
    from api_utils import login_goodwe
    from api_utils import fetch_variable
    from decimal import Decimal, getcontext

    # 设置全局精度
    getcontext().prec = 15

    # 环境变量
    username = "18834175317"

    # ============test============
    base_url = "https://test.we.goodwe.com"
    password = "Aa123456" # test
    sql_host = '10.197.12.7'
    sql_user = "sebu_test_01"
    sql_pwd = "r%iGKeCsSFu4PYs5"
    # ============uat============
    # base_url = "https://uat.we.goodwe.com"
    # password = "Duhuixia612." # uat
    # sql_host = '10.197.13.7'
    # sql_user = "postgres"
    # sql_pwd = "Goodwe123small"

    # 公共变量
    asset_id = "1798275722721230848"
    month = "2026-03-01"
    startDt = month
    endDt = month
    ##查询公式的月度周期
    start_date = "2026-03-01"
    end_date = "2026-03-31"
    # ===== 在程序启动时登录一次 =====
    session = login_goodwe(
        base_url=base_url,
        account=username,
        password=password
    )

    if session:
        print("✅ Session 已就绪")
        print(f"Authorization: {session.headers.get('Authorization')}")
    else:
        print("❌ 登录失败")

    # ========== 参数配置 ==========
    # ===== 系统级指标：priceMonthAvgRealTime / aRealTime / purchaseAvgPrice，获取方式相同 =====
    system_indicators = ["priceMonthAvgRealTime", "aRealTime", "purchaseAvgPrice"]
    sys_values = {}
    for code in system_indicators:
        context = {
            "variableCode": code,
            "endDt": "2026-03-01",
            "startDt": "2026-03-01",
            "tag": code,
            "dimension": "month",
            "provinceId": "330000",
            "code": "m",
            "index": "0",
            "tagCode": code
        }
        result = fetch_variable(session, context, base_url)
        if result.get("code") == "00000":
            sys_values[code] = Decimal(str(result["data"]["value"]))
            print(f"✅ 获取到{code}值: {sys_values[code]}")
        else:
            print(f"❌ 获取{code}失败:", result.get("description"))

    priceMonthAvgRealTime = sys_values["priceMonthAvgRealTime"]
    aRealTime = sys_values["aRealTime"]
    purchaseAvgPrice = sys_values["purchaseAvgPrice"]

    ##登录数据库
    conn_params = {
        "dbname": "secp",
        "port": 5432,
        "user": sql_user,
        "password": sql_pwd,
        "host": sql_host
    }

    # 建立连接
    conn = psycopg2.connect(**conn_params)
    print("✅ PostgreSQL连接成功!")
    # 创建游标
    cursor = conn.cursor()
    cursor.execute("""
            SELECT manual_inputs_variables
            FROM deal_covenant.custom_rule_price_info AS crpi
            WHERE custom_rule_id IN (
                SELECT id FROM deal_covenant.custom_rule_info
                WHERE asset_id = %s
                AND start_date >= %s
                AND end_date <= %s
            )
            AND category_code IN ('Retail')
        """, (asset_id, start_date, end_date))
    rows = cursor.fetchall()  # 获取所有记录
    # 取出第一个元素（元组）
    item = rows[0]
    # 取出元组中的第一个元素（字典）
    variables = item[0]

    # 获取用户级参数（从数据库 manual_inputs_variables 获取）
    user_vars = [
        "k_midterm", "k_spot", "dp_float",
        "k_fixed", "p_fixed", "k_float",
    ]
    variables = {code: Decimal(str(variables[code])) for code in user_vars}
    for code, value in variables.items():
        print(f"{code}: {value}")
    # 关闭连接
    cursor.close()
    conn.close()

    # ========== 零售套餐公式计算 ==========
    # linkagePrice = k_midterm*priceMonthAvgRealTime + k_spot*aRealTime + dp_float
    # P零售 = k_fixed*p_fixed + k_float*linkagePrice
    linkage_price = (
        variables["k_midterm"] * priceMonthAvgRealTime
        + variables["k_spot"] * aRealTime
        + variables["dp_float"]
    )
    final_price = variables["k_fixed"] * variables["p_fixed"] + variables["k_float"] * linkage_price

    # ========== 输出结果 ==========
    print(f"联动价 (linkagePrice): {linkage_price}")
    print(f"-----零售电价--------")
    print(f"最终交易价格(零售电价实际): {final_price}")

    # 计算购电电价
    PurchaseAlg = final_price
    print(f"-----购电电价--------")
    print(f"购电电价实际: {PurchaseAlg}")

    # ========== 获取各时段浮动系数 floatFactor ==========
    # 尖:critical 峰:peak 平:flat 谷:valley 深谷:deep
    # electricity_type：0-一般工商业/1-大型工业 voltage_level_type：0-单一制/1-两部制 voltage_level_sub_type：1-100千伏以上/2-100千伏以下
    periods = {
        "critical": "尖峰",
        "peak": "峰",
        "flat": "平",
        "valley": "谷",
        "deep": "深谷",
    }
    float_factor = {}
    conn = psycopg2.connect(**conn_params)
    print("✅ PostgreSQL连接成功!")
    cursor = conn.cursor()
    for code, label in periods.items():
        cursor.execute("""
                SELECT pvv.*
                FROM e_price_template.price_variable_value AS pvv
                WHERE province_code = %s
                    AND month = %s
                    AND electricity_type = '0'
                    AND voltage_level_type = '1'
                    AND voltage_value_code = '14'
                    AND variable_code = %s
            """, ("320000", month, code))
        rows = cursor.fetchall()
        if not rows:
            print(f"⚠️ {label}段({code}): 未查到 floatFactor")
            float_factor[code] = None
        else:
            col_names = [d[0] for d in cursor.description]
            value = dict(zip(col_names, rows[0]))["variable_value"]
            if value is None:
                print(f"⚠️ {label}段({code}): floatFactor 值为空(NULL)，跳过计算")
                float_factor[code] = None
            else:
                float_factor[code] = Decimal(str(value))
                print(f"{label}段({code}) floatFactor: {float_factor[code]}")
    cursor.close()
    conn.close()

    # ========== 获取电价模板五大项价格 ==========
    # 建立连接
    conn = psycopg2.connect(**conn_params)
    print("✅ PostgreSQL连接成功!")
    # 创建游标
    cursor = conn.cursor()
    cursor.execute("""
            SELECT ptspr.price
            FROM covenant.price_template_stage_price_rel ptspr
            JOIN covenant.price_template_asset_rel ptar
                ON ptspr.price_template_id = ptar.price_template_id
            WHERE ptar.asset_id = %s
                AND ptar.price_sub_category_code = 'StateGridAgentCost'
                AND ptar.start_date = %s
                AND ptspr.price_type = 'OutLineLoss'
        """, (asset_id, start_date))
    rows = cursor.fetchall()
    outLineLossPrice = Decimal(str(rows[0][0]))
    print(f"outLineLossPrice: {outLineLossPrice}")
    cursor.execute("""
                SELECT ptspr.price
                FROM covenant.price_template_stage_price_rel ptspr
                JOIN covenant.price_template_asset_rel ptar
                    ON ptspr.price_template_id = ptar.price_template_id
                WHERE ptar.asset_id = %s
                    AND ptar.price_sub_category_code = 'StateGridAgentCost'
                    AND ptar.start_date = %s
                    AND ptspr.price_type = 'UnitConvey'
            """, (asset_id, start_date))
    rows = cursor.fetchall()
    unitConveyPrice = Decimal(str(rows[0][0]))
    print(f"unitConveyPrice: {unitConveyPrice}")

    cursor.execute("""
                SELECT ptspr.price
                FROM covenant.price_template_stage_price_rel ptspr
                JOIN covenant.price_template_asset_rel ptar
                    ON ptspr.price_template_id = ptar.price_template_id
                WHERE ptar.asset_id = %s
                    AND ptar.price_sub_category_code = 'StateGridAgentCost'
                    AND ptar.start_date = %s
                    AND ptspr.price_type = 'SysOperateFee'
            """, (asset_id, start_date))
    rows = cursor.fetchall()
    sysOperateFeePrice = Decimal(str(rows[0][0]))
    print(f"sysOperateFeePrice: {sysOperateFeePrice}")

    cursor.execute("""
                SELECT ptspr.price
                FROM covenant.price_template_stage_price_rel ptspr
                JOIN covenant.price_template_asset_rel ptar
                    ON ptspr.price_template_id = ptar.price_template_id
                WHERE ptar.asset_id = %s
                    AND ptar.price_sub_category_code = 'StateGridAgentCost'
                    AND ptar.start_date = %s
                    AND ptspr.price_type = 'GovernmentAppend'
            """, (asset_id, start_date))
    rows = cursor.fetchall()
    governmentAppendPrice = Decimal(str(rows[0][0]))
    print(f"governmentAppendPrice: {governmentAppendPrice}")

    cursor.execute("""
                SELECT ptspr.price
                FROM covenant.price_template_stage_price_rel ptspr
                JOIN covenant.price_template_asset_rel ptar
                    ON ptspr.price_template_id = ptar.price_template_id
                WHERE ptar.asset_id = %s
                    AND ptar.price_sub_category_code = 'StateGridAgentCost'
                    AND ptar.start_date = %s
                    AND ptspr.price_type = 'Other'
            """, (asset_id, start_date))
    rows = cursor.fetchall()
    otherPrice = Decimal(str(rows[0][0]))
    print(f"otherPrice: {otherPrice}")
    # 关闭连接
    cursor.close()
    conn.close()

    # 电价模板五大项合计
    five_items = (
            unitConveyPrice
            + outLineLossPrice
            + sysOperateFeePrice
            + governmentAppendPrice
            + otherPrice
    )
    print(f"电价模板五大项合计电价: {five_items}")

    # ========== 计算到户电价 ==========
    # P到户 = PurchaseAlg * floatFactor + outLineLossPrice + unitConveyPrice
    #        + sysOperateFeePrice + governmentAppendPrice + otherPrice
    print(f"-----到户电价--------")
    print("\n📊 到户电价预测:")
    for code, label in periods.items():
        if float_factor[code] is None:
            print(f"  {label}段: ⚠️ 无 floatFactor 数据，跳过计算")
            continue
        reach_price = PurchaseAlg * float_factor[code] + five_items
        print(f"  {label}段({code}): {reach_price}")
