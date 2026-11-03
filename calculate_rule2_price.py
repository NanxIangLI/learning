#### 规则2非分时 固定+比例分成计算：
'''
P零售 = {if(priceMonthAvgRealTime<p_ref){
        longtermPrice=p_ref+k_down_midterm*(p_ref-priceMonthAvgRealTime);
        }else{
        longtermPrice=p_ref+k_up_midterm*(priceMonthAvgRealTime-p_ref);
        }
        if(aRealTime<p_ref){
        realtimePrice=p_ref+k_down_spot*(p_ref-aRealTime);
        }else{
        realtimePrice=p_ref+k_up_spot*(aRealTime-p_ref);
        }
        splitPrice=share_k_midterm*longtermPrice+share_k_spot*realtimePrice;
        portfolioPrice=k_fixed*p_fixed+k_share*splitPrice;
        capPrice=(1+cap_price_percent)*purchaseAvgPrice;
        MinPair(portfolioPrice,capPrice)}
P绿电 = {floatPrice=green_k_year*greenElectricityPrice+green_k_month*greenElectricityMonthlyAPrice+green_k_inmonth*greenElectricityIntraMonthPrice+green_dp_float;
        MinPair(floatPrice,green_price_cap)}
P绿电综合 = GreenElectric + GreenEnv
P到户 = Purchase*floatFactor+outLineLossPrice+unitConveyPrice+sysOperateFeePrice+governmentAppendPrice+otherPrice
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
    asset_id = "2094605881445646336"
    month = "2026-07-01"
    startDt = month
    endDt = month
    ##查询公式的月度周期
    start_date = "2026-07-01"
    end_date = "2026-07-31"
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
    # ===== 系统级指标：公式变量名 -> (接口 variableCode, dimension)
    #       接口码定义见 e_price_template.price_variable_source_config =====
    indicator_code_map = {
        "priceMonthAvgRealTime": ("averagePriceRealTime", "month"),
        "aRealTime": ("aRealTime", "month"),
        "purchaseAvgPrice": ("aAvgRealTime", "month"),
        "GreenEnv": ("greenEnvRealTime", "month"),
        "greenElectricityPrice": ("greenPowerAnnualAvgRealTime", "year"),
        "greenElectricityMonthlyAPrice": ("greenPowerMonthlyAvgRealTime", "month"),
        "greenElectricityIntraMonthPrice": ("greenPowerIntraMonthAvgRealTime", "month"),
    }
    sys_values = {}
    for name, (code, dimension) in indicator_code_map.items():
        context = {
            "variableCode": code,
            "endDt": "2026-07-01",
            "startDt": "2026-07-01",
            "tag": code,
            "dimension": dimension,
            "provinceId": "320000",
            "code": "m",
            "index": "0",
            "tagCode": code
        }
        result = fetch_variable(session, context, base_url)
        if result.get("code") == "00000" and isinstance(result.get("data"), dict) and result["data"].get("value") is not None:
            sys_values[name] = Decimal(str(result["data"]["value"]))
            print(f"✅ 获取到{name}({code})值: {sys_values[name]}")
        else:
            print(f"❌ 获取{name}({code})失败:", result.get("description"), result.get("data"))

    missing_indicators = [n for n in indicator_code_map if n not in sys_values]
    if missing_indicators:
        raise ValueError(f"以下系统级指标获取失败: {missing_indicators}")

    priceMonthAvgRealTime = sys_values["priceMonthAvgRealTime"]
    aRealTime = sys_values["aRealTime"]
    purchaseAvgPrice = sys_values["purchaseAvgPrice"]
    GreenEnv = sys_values["GreenEnv"]
    greenElectricityPrice = sys_values["greenElectricityPrice"]
    greenElectricityMonthlyAPrice = sys_values["greenElectricityMonthlyAPrice"]
    greenElectricityIntraMonthPrice = sys_values["greenElectricityIntraMonthPrice"]

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
    # 零售参数取自 category_code='Retail'，绿电参数取自 category_code='GreenElectric'
    cursor.execute("""
            SELECT category_code, manual_inputs_variables
            FROM deal_covenant.custom_rule_price_info AS crpi
            WHERE custom_rule_id IN (
                SELECT id FROM deal_covenant.custom_rule_info
                WHERE asset_id = %s
                AND start_date >= %s
                AND end_date <= %s
            )
            AND category_code IN ('Retail', 'GreenElectric')
        """, (asset_id, start_date, end_date))
    rows = cursor.fetchall()  # 获取所有记录

    # 按 category_code 归集各品类的 manual_inputs_variables
    raw_vars = {}
    for category_code, manual_inputs in rows:
        if not manual_inputs:
            print(f"⚠️ {category_code} 的 manual_inputs_variables 为空，跳过")
            continue
        if category_code == 'GreenElectric':
            print(f"✅ 绿电参数来自 category_code={category_code}")
        raw_vars.update(manual_inputs)

    if not raw_vars:
        raise ValueError(
            f"未查询到 Retail / GreenElectric 的 manual_inputs_variables 数据: "
            f"asset_id={asset_id}, start_date={start_date}, end_date={end_date}"
        )

    # 获取用户级参数（从数据库 manual_inputs_variables 获取）
    # p_ref/k_*/share_k_*/cap_price_percent 来自 Retail；green_* 来自 GreenElectric
    user_vars = [
        "p_ref", "k_down_midterm", "k_up_midterm",
        "k_down_spot", "k_up_spot",
        "share_k_midterm", "share_k_spot",
        "k_fixed", "p_fixed", "k_share",
        "cap_price_percent",
        "green_k_year", "green_k_month", "green_k_inmonth", "green_dp_float",
        "green_price_cap",
    ]
    missing = [code for code in user_vars if code not in raw_vars]
    if missing:
        raise KeyError(f"manual_inputs_variables 中缺少以下参数: {missing}")
    variables = {code: Decimal(str(raw_vars[code])) for code in user_vars}
    for code, value in variables.items():
        print(f"{code}: {value}")
    # 关闭连接
    cursor.close()
    conn.close()

    # ========== 零售套餐公式计算 ==========
    # priceMonthAvgRealTime < p_ref -> 下浮系数，否则上浮系数（实时同理）
    if priceMonthAvgRealTime < variables["p_ref"]:
        longterm_price = variables["p_ref"] + variables["k_down_midterm"] * (variables["p_ref"] - priceMonthAvgRealTime)
    else:
        longterm_price = variables["p_ref"] + variables["k_up_midterm"] * (priceMonthAvgRealTime - variables["p_ref"])

    if aRealTime < variables["p_ref"]:
        realtime_price = variables["p_ref"] + variables["k_down_spot"] * (variables["p_ref"] - aRealTime)
    else:
        realtime_price = variables["p_ref"] + variables["k_up_spot"] * (aRealTime - variables["p_ref"])

    split_price = variables["share_k_midterm"] * longterm_price + variables["share_k_spot"] * realtime_price
    portfolio_price = variables["k_fixed"] * variables["p_fixed"] + variables["k_share"] * split_price
    cap_price = (Decimal("1") + variables["cap_price_percent"]) * purchaseAvgPrice

    # MinPair: 取组合价与上限价的较小值
    final_price = min(portfolio_price, cap_price)

    # ========== 输出结果 ==========
    print(f"长协折算价 (longtermPrice): {longterm_price}")
    print(f"现货折算价 (realtimePrice): {realtime_price}")
    print(f"分摊价 (splitPrice): {split_price}")
    print(f"组合价 (portfolioPrice): {portfolio_price}")
    print(f"上限价格 (capPrice): {cap_price}")
    print(f"-----零售电价--------")
    print(f"最终交易价格(零售电价实际): {final_price}")

    # ========== 绿电电价计算 ==========
    # floatPrice = green_k_year*greenElectricityPrice + green_k_month*greenElectricityMonthlyAPrice
    #            + green_k_inmonth*greenElectricityIntraMonthPrice + green_dp_float
    # GreenElectric(绿电电价) = MinPair(floatPrice, green_price_cap)
    float_price = (
        variables["green_k_year"] * greenElectricityPrice
        + variables["green_k_month"] * greenElectricityMonthlyAPrice
        + variables["green_k_inmonth"] * greenElectricityIntraMonthPrice
        + variables["green_dp_float"]
    )
    GreenElectric = min(float_price, variables["green_price_cap"])
    print(f"-----绿电电价--------")
    print(f"绿电浮动价 (floatPrice): {float_price}")
    print(f"绿电价格上限 (green_price_cap): {variables['green_price_cap']}")
    print(f"绿电电价 (GreenElectric): {GreenElectric}")
    print(f"绿电环境电价 (GreenEnv): {GreenEnv}")

    # ========== 绿电综合价计算 ==========
    # P绿电综合 = GreenElectric + GreenEnv
    green_total_price = GreenElectric + GreenEnv
    print(f"-----绿电综合电价--------")
    print(f"绿电综合电价 (P绿电综合): {green_total_price}")

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
    # P到户 = Purchase * floatFactor + outLineLossPrice + unitConveyPrice
    #        + sysOperateFeePrice + governmentAppendPrice + otherPrice
    print(f"-----到户电价--------")
    print("\n📊 到户电价预测:")
    for code, label in periods.items():
        if float_factor[code] is None:
            print(f"  {label}段: ⚠️ 无 floatFactor 数据，跳过计算")
            continue
        reach_price = PurchaseAlg * float_factor[code] + five_items
        print(f"  {label}段({code}): {reach_price}")
