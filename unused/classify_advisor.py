from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import duckdb

#分类器

DEFAULT_INPUT = Path(
    r"E:\学习资料\研\我的论文\金融科技\第二章论文\标注数据\advisor_recall_weighted_pool_sample_2014_2026.csv"
)
CLASSIFIER_VERSION = "dict_v0_advisor_20260611"
DICT_FIELDS = [
    "advisor_job_dict",
    "advisor_scope_dict",
    "advisor_type_dict",
    "function_tags_dict",
    "quote_span_dict",
    "key_evidence_dict",
    "negative_chain_dict",
    "confidence_dict",
    "review_flag",
    "train_eligible_dict",
    "train_role_dict",
    "rule_id_dict",
    "pos_hits_dict",
    "neg_hits_dict",
    "classifier_version",
]
SUMMARY_FIELDS = [
    "sample_pool",
    "advisor_recall_level",
    "advisor_job_dict",
    "confidence_dict",
    "review_flag",
    "train_role_dict",
    "rule_id_dict",
    "count",
]
TEXT_COLUMNS = ["招聘岗位", "职位描述"]
MATCH_A_COL = "match_a_terms"
MATCH_D_COL = "match_d_terms"


STRONG_ADVISOR_TITLE_TERMS = [
    "证券投资顾问",
    "证券投顾",
    "基金投顾",
    "基金投资顾问",
    "投顾经理",
    "投顾服务经理",
    "投顾业务经理",
    "投资顾问岗",
    "证券投资顾问岗",
    "投资顾问",
]
R0_STRONG_EMPTY_TITLE_TERMS = ["证券投资顾问", "基金投顾", "基金投资顾问", "投资顾问岗", "投顾经理"]
R0_WEAK_EMPTY_TITLE_TERMS = ["理财顾问", "财富顾问", "客户经理", "理财经理", "私人银行", "relationship manager"]
ASSISTANT_TERMS = ["投资顾问助理", "投顾助理", "财富顾问助理", "助理财富顾问", "理财顾问助理"]
FINANCE_DOMAIN_TERMS = [
    "证券",
    "基金",
    "公募",
    "私募",
    "财富管理",
    "理财",
    "资产配置",
    "投资咨询",
    "投顾",
    "基金投顾",
    "证券营业部",
    "营业部",
    "券商",
    "银行财富",
    "私人银行",
    "高净值客户",
    "金融产品",
    "理财产品",
    "股票",
    "债券",
    "fof",
    "基金组合",
]
CLIENT_NEED_TERMS = [
    "客户风险",
    "风险偏好",
    "风险承受能力",
    "投资目标",
    "投资需求",
    "客户需求",
    "客户资产",
    "资产状况",
    "财务状况",
    "收益目标",
    "投资经验",
    "高净值客户需求",
    "kyc",
    "客户画像",
    "客户分层",
    "适当性评估",
]
ADVICE_OUTPUT_TERMS = [
    "投资建议",
    "资产配置",
    "资产配置方案",
    "资产配置建议",
    "组合配置",
    "投资组合",
    "基金组合",
    "产品组合",
    "理财规划",
    "财富规划",
    "理财方案",
    "投资规划",
    "账户诊断",
    "投后服务",
    "投后陪伴",
    "组合跟踪",
    "风险解释",
    "策略解释",
    "配置建议",
]
SUPPORT_STRATEGY_TERMS = [
    "投顾组合",
    "基金投顾组合",
    "基金投顾策略",
    "投顾策略",
    "组合策略",
    "资产配置策略",
    "基金备选库",
    "基金池",
    "基金评价",
    "基金筛选",
    "组合调仓建议",
    "再平衡",
    "策略说明",
    "投研支持",
    "投资建议依据",
    "客户资产配置服务",
    "投顾服务团队",
]
STRATEGY_OBJECT_TERMS = ["投顾组合", "基金投顾", "客户投资建议", "资产配置服务", "投顾服务团队", "投顾策略说明", "客户资产配置服务"]
ROBO_ADVISOR_TERMS = [
    "智能投顾",
    "投顾平台",
    "基金投顾平台",
    "投顾系统",
    "投顾工作台",
    "投顾crm",
    "投顾服务平台",
    "组合生成",
    "风险测评",
    "再平衡",
    "模型输出解释",
    "投顾留痕",
    "投资建议留痕",
]
ROBO_PLATFORM_TERMS = ["智能投顾", "投顾平台", "基金投顾平台", "投顾系统", "投顾工作台"]
ROBO_MODULE_TERMS = ["风险测评", "客户画像", "组合生成", "资产配置", "再平衡", "投资建议", "投顾留痕", "模型输出解释", "投后服务"]
COMPLIANCE_SERVICE_TERMS = [
    "适当性",
    "适当性管理",
    "风险揭示",
    "服务协议",
    "投顾服务协议",
    "客户回访",
    "投诉处理",
    "留痕",
    "录音录像",
    "资料保存",
    "服务质量",
    "信息披露",
    "客户告知",
    "投资建议记录",
    "异常交易预警",
    "服务终止",
]
COMPLIANCE_OBJECT_TERMS = ["投顾业务", "基金投顾", "投资建议", "投顾组合", "投顾服务协议", "客户授权账户", "智能投顾系统", "投顾服务流程"]
MANAGED_FUND_OPS_TERMS = [
    "管理型基金投顾",
    "客户授权账户",
    "授权范围",
    "客户委托",
    "代理客户决策",
    "投顾账户",
    "投顾组合调仓",
    "组合调仓",
    "再平衡",
    "基金申购",
    "基金赎回",
    "申购赎回转换",
    "持仓披露",
    "运作报告",
    "异常交易监控",
    "服务终止操作",
]
MANAGED_FUND_GROUPS = [
    ["管理型基金投顾", "基金投顾", "投顾组合", "投顾账户"],
    ["客户授权账户", "授权范围", "客户委托", "代理客户决策"],
    ["组合调仓", "再平衡", "申购赎回转换", "持仓披露", "异常交易预警", "服务终止"],
]
MANAGEMENT_TERMS = [
    "投顾团队管理",
    "投顾业务管理",
    "投顾业务推动",
    "投顾服务体系",
    "投顾服务流程",
    "投顾服务质量",
    "投顾人员培训",
    "投顾培训",
    "资产配置服务体系",
    "投顾业务规划",
    "投顾服务策略",
]
MANAGEMENT_OBJECT_TERMS = ["投顾业务", "投顾团队", "投顾服务质量", "资产配置服务体系", "投顾服务流程", "投顾人员培训"]
HARD_NEG_REAL_ESTATE_TERMS = [
    "房地产",
    "房产",
    "置业顾问",
    "房地产投资顾问",
    "一手房投资顾问",
    "世华房地产投资顾问",
    "二手房",
    "商业地产",
    "楼盘",
    "带看",
    "房屋租赁",
    "房产权证",
    "按揭",
    "房产经纪",
    "房产销售",
    "营销代理",
    "楼盘销售",
]
HARD_NEG_SALES_TERMS = [
    "产品销售",
    "理财产品销售",
    "基金销售",
    "保险销售",
    "贷款销售",
    "信用卡推广",
    "客户开发",
    "开发客户",
    "客户开拓",
    "开户",
    "开户转化",
    "渠道拓展",
    "电话营销",
    "陌拜",
    "销售任务",
    "销售目标",
    "业绩指标",
    "销售业绩",
    "转化率",
    "营销活动",
    "获客",
    "拉新",
]
HARD_NEG_RESEARCH_TERMS = [
    "行业研究",
    "公司研究",
    "宏观研究",
    "策略研究",
    "信用研究",
    "商品研究",
    "研究报告",
    "市场观点",
    "投资评级",
    "机构路演",
    "路演",
    "上市公司调研",
    "卖方研究",
    "股票推荐报告",
]
HARD_NEG_IT_CRM_TERMS = [
    "app",
    "产品经理",
    "crm",
    "用户增长",
    "智能推荐",
    "营销系统",
    "客户触达",
    "流量运营",
    "活动推荐",
    "资讯推荐",
    "广告推荐",
    "数据平台",
    "数据仓库",
    "系统开发",
    "后端开发",
    "java",
    "算法工程师",
    "推荐算法",
]
HARD_NEG_FUND_OPS_TERMS = ["ta", "注册登记", "清算", "估值", "份额登记", "交易数据核对", "普通申购", "普通赎回", "账户处理"]
HARD_NEG_CONTENT_TERMS = ["公众号", "财经内容", "投教", "投资者教育", "课程", "直播", "讲师", "市场评论", "内容运营", "品牌宣传", "活动宣讲"]
HARD_NEG_FUTURES_TERMS = ["期货", "期权", "衍生品", "套保", "套利", "产业客户", "风险管理咨询", "期货交易"]
ASSISTANT_POS_TERMS = ["风险识别", "资产配置建议", "投资建议解释", "组合跟踪", "投后陪伴", "投顾留痕", "风险揭示", "适当性", "投顾服务协议", "回访", "服务终止"]
ADVISORY_SIGNING_TERMS = ["投顾产品推广", "投顾签约", "投顾协议签约", "协助签订投顾服务协议", "宣传投顾产品", "推送投顾产品"]
ADVISORY_SIGNING_POS_TERMS = ["风险揭示", "适当性", "投资建议", "投后服务", "客户回访", "留痕管理", "服务终止"]
WEAK_SIGNAL_TERMS = [
    "理财顾问",
    "财富顾问",
    "理财经理",
    "客户经理",
    "私人银行",
    "财富管理",
    "财富中心",
    "高净值客户",
    "家族信托",
    "教育金规划",
    "财富传承",
    "财富规划",
    "资产配置报告",
    "目标风险",
    "风险预算",
]
ORDINARY_RESEARCH_ONLY_TERMS = ["基金研究", "基金池", "基金评价", "产品准入", "基金备选库"]
CRM_HARD_NEG_CHAIN = ["客户画像", "产品推荐", "营销触达", "转化率提升"]
SALES_MANAGEMENT_TERMS = ["销售团队管理", "渠道管理", "客户开发指标管理", "销售管理"]
ADVISOR_WEAK_POS_TERMS = ["投资顾问", "理财顾问", "财富顾问", "投顾产品", "投顾签约"]


@dataclass
class Result:
    advisor_job_dict: str = "0"
    advisor_scope_dict: str = "non_advisory"
    advisor_type_dict: str = "N_non_adviser"
    function_tags_dict: str = ""
    quote_span_dict: str = ""
    key_evidence_dict: str = ""
    negative_chain_dict: str = ""
    confidence_dict: str = "high"
    review_flag: str = "0"
    train_eligible_dict: str = "1"
    train_role_dict: str = "gold_negative"
    rule_id_dict: str = "R17_DEFAULT_NEGATIVE"
    pos_hits_dict: str = ""
    neg_hits_dict: str = ""
    classifier_version: str = CLASSIFIER_VERSION

    def as_dict(self) -> dict[str, str]:
        return {field: str(getattr(self, field)) for field in DICT_FIELDS}


def normalize_text(x: object) -> str:
    if x is None:
        return ""
    text = str(x)
    if text.lower() == "nan":
        return ""
    text = text.replace("\u3000", " ")
    text = text.replace("；", ";").replace("、", ",").replace("，", ",")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def split_terms(x: object) -> list[str]:
    text = normalize_text(x)
    if not text:
        return []
    return [part.strip() for part in re.split(r"[;；]", text) if part.strip()]


def contains_any(text: str, terms: Iterable[str]) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(term) in normalized for term in terms)


def count_hits(text: str, terms: Iterable[str]) -> list[str]:
    normalized = normalize_text(text)
    hits = []
    seen = set()
    for term in terms:
        term_norm = normalize_text(term)
        if term_norm and term_norm in normalized and term not in seen:
            hits.append(term)
            seen.add(term)
    return hits


def is_description_empty(text: object) -> bool:
    return len(normalize_text(text)) < 20


def make_quote_span(text: str, hit_terms: Iterable[str]) -> str:
    source = re.sub(r"\s+", " ", "" if text is None else str(text)).strip()
    if not source:
        return ""
    terms = [str(term) for term in hit_terms if str(term)]
    anchors = ["岗位职责", "工作职责", "职位描述", "任职要求"]
    positions: list[tuple[int, str]] = []
    for term in terms:
        idx = source.lower().find(term.lower())
        if idx >= 0:
            bonus = 0
            for anchor in anchors:
                anchor_idx = source.find(anchor)
                if anchor_idx >= 0 and abs(anchor_idx - idx) <= 180:
                    bonus = -10000
                    break
            positions.append((bonus + idx, term))
    if not positions:
        return source[:80]
    spans = []
    used = set()
    for _, term in sorted(positions)[:3]:
        idx = source.lower().find(term.lower())
        if idx < 0:
            continue
        start = max(0, idx - 30)
        end = min(len(source), idx + len(term) + 50)
        span = source[start:end]
        if span not in used:
            spans.append(span)
            used.add(span)
    return "；".join(spans[:3])


def detect_encoding(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with path.open("r", encoding=encoding, newline="") as f:
                f.read(4096)
            return encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("csv", b"", 0, 1, f"Cannot decode {path}")


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def read_header(path: Path, encoding: str) -> list[str]:
    with path.open("r", encoding=encoding, newline="") as f:
        header = next(csv.reader(f))
    return [col for col in header if col]


def validate_input_with_duckdb(path: Path, encoding: str) -> tuple[list[str], int]:
    header = read_header(path, encoding)
    missing = [col for col in TEXT_COLUMNS if col not in header]
    if missing:
        raise ValueError(f"Input missing required columns: {missing}")
    con = duckdb.connect(database=":memory:")
    try:
        row_count = con.execute(
            f"""
            SELECT count(*)
            FROM read_csv_auto(
                {sql_literal(str(path))},
                header = true,
                all_varchar = true,
                ignore_errors = true,
                union_by_name = true,
                encoding = 'utf-8'
            )
            """
        ).fetchone()[0]
    except duckdb.Error:
        # DuckDB is still used for UTF-8 inputs; gb18030 fallback is handled by Python csv.
        if encoding != "gb18030":
            raise
        with path.open("r", encoding=encoding, newline="") as f:
            row_count = sum(1 for _ in csv.DictReader(f))
    finally:
        con.close()
    return header, int(row_count)


def combined_text(row: dict[str, str]) -> str:
    return normalize_text((row.get("招聘岗位") or "") + " " + (row.get("职位描述") or ""))


def quote_from_row(row: dict[str, str], hits: list[str]) -> str:
    desc_quote = make_quote_span(row.get("职位描述", ""), hits)
    title_quote = make_quote_span(row.get("招聘岗位", ""), hits)
    if desc_quote and title_quote:
        return title_quote + "；" + desc_quote
    return desc_quote or title_quote


def set_common_hits(result: Result, row: dict[str, str], pos_terms: Iterable[str], neg_terms: Iterable[str]) -> Result:
    text = combined_text(row)
    pos_hits = count_hits(text, pos_terms)
    neg_hits = count_hits(text, neg_terms)
    result.pos_hits_dict = ";".join(pos_hits)
    result.neg_hits_dict = ";".join(neg_hits)
    result.quote_span_dict = quote_from_row(row, pos_hits or neg_hits)
    return result


def positive_finance_chain(text: str) -> bool:
    return contains_any(text, FINANCE_DOMAIN_TERMS) and contains_any(text, CLIENT_NEED_TERMS) and contains_any(text, ADVICE_OUTPUT_TERMS)


def strategy_object_chain(text: str) -> bool:
    return contains_any(text, STRATEGY_OBJECT_TERMS)


def robo_module_chain(text: str) -> bool:
    return contains_any(text, ROBO_PLATFORM_TERMS) and contains_any(text, ROBO_MODULE_TERMS)


def compliance_object_chain(text: str) -> bool:
    return contains_any(text, COMPLIANCE_SERVICE_TERMS) and contains_any(text, COMPLIANCE_OBJECT_TERMS)


def managed_fund_chain(text: str) -> bool:
    return sum(1 for group in MANAGED_FUND_GROUPS if contains_any(text, group)) >= 2


def management_chain(text: str) -> bool:
    return contains_any(text, MANAGEMENT_TERMS) and contains_any(text, MANAGEMENT_OBJECT_TERMS)


def any_positive_chain(text: str) -> bool:
    return (
        positive_finance_chain(text)
        or (contains_any(text, SUPPORT_STRATEGY_TERMS) and strategy_object_chain(text))
        or robo_module_chain(text)
        or compliance_object_chain(text)
        or managed_fund_chain(text)
        or management_chain(text)
    )


def audit_match_a_terms(row: dict[str, str]) -> str:
    match_a = split_terms(row.get(MATCH_A_COL, ""))
    match_d = split_terms(row.get(MATCH_D_COL, ""))
    desc = normalize_text(row.get("职位描述", ""))
    strong_terms = ["证券投资顾问", "基金投顾", "基金投资顾问"]
    task_terms = ["投资建议", "资产配置", "风险承受能力", "组合服务", "投后服务"]
    if "投资顾问" in match_a and match_d:
        return "A_INVESTMENT_ADVISOR_WITH_D_NEG_REVIEW"
    if any(term in match_a for term in strong_terms) and contains_any(desc, task_terms):
        return "A_STRONG_FINANCE_WITH_TASK"
    if match_a == ["投资顾问"] and is_description_empty(desc):
        return "A_ONLY_INVESTMENT_ADVISOR_EMPTY_DESC"
    if any(term in match_a for term in ["投资顾问助理", "投顾助理"]):
        return "A_ASSISTANT_REVIEW"
    return ""


def classify_row(row: dict[str, str]) -> Result:
    title = normalize_text(row.get("招聘岗位", ""))
    desc = normalize_text(row.get("职位描述", ""))
    text = normalize_text(title + " " + desc)
    match_a_audit = audit_match_a_terms(row)

    finance_hits = count_hits(text, FINANCE_DOMAIN_TERMS)
    client_hits = count_hits(text, CLIENT_NEED_TERMS)
    advice_hits = count_hits(text, ADVICE_OUTPUT_TERMS)
    positive_chain = positive_finance_chain(text)
    full_pos_hits = finance_hits + client_hits + advice_hits

    if is_description_empty(desc):
        if contains_any(title, R0_STRONG_EMPTY_TITLE_TERMS):
            result = Result(
                advisor_job_dict="1",
                advisor_scope_dict="core_frontline",
                advisor_type_dict="A_frontline_client_adviser",
                confidence_dict="low",
                review_flag="1",
                train_eligible_dict="0",
                train_role_dict="review_exclude",
                rule_id_dict="R0_STRONG_TITLE_EMPTY_DESC",
                key_evidence_dict="岗位名称强信号，但职责不足，需要人工复核",
                pos_hits_dict=";".join(count_hits(title, R0_STRONG_EMPTY_TITLE_TERMS)),
            )
            result.quote_span_dict = quote_from_row(row, split_terms(result.pos_hits_dict))
            return result
        if contains_any(title, R0_WEAK_EMPTY_TITLE_TERMS):
            result = Result(
                advisor_job_dict="0",
                advisor_scope_dict="non_advisory",
                advisor_type_dict="R_boundary_review",
                confidence_dict="low",
                review_flag="1",
                train_eligible_dict="0",
                train_role_dict="review_exclude",
                rule_id_dict="R0_WEAK_TITLE_EMPTY_DESC",
                neg_hits_dict=";".join(count_hits(title, R0_WEAK_EMPTY_TITLE_TERMS)),
            )
            result.quote_span_dict = quote_from_row(row, split_terms(result.neg_hits_dict))
            return result
        result = Result(rule_id_dict="R0_EMPTY_NO_SIGNAL", negative_chain_dict="职责为空或过短，且岗位名称无投顾强信号")
        return set_common_hits(result, row, [], [])

    if contains_any(text, HARD_NEG_REAL_ESTATE_TERMS) and not any_positive_chain(text):
        result = Result(
            train_role_dict="hard_negative",
            negative_chain_dict="投资顾问相关词被房地产/置业/房产经纪语境污染，无证券、基金或财富管理投顾任务链",
            rule_id_dict="R1_REAL_ESTATE_LOCK",
        )
        return set_common_hits(result, row, [], HARD_NEG_REAL_ESTATE_TERMS)

    if contains_any(text, HARD_NEG_FUTURES_TERMS) and not (
        contains_any(text, ["证券", "基金", "财富管理", "投顾组合", "基金投顾服务", "客户综合资产配置"])
    ):
        result = Result(
            advisor_type_dict="R_boundary_review",
            confidence_dict="medium",
            review_flag="1",
            train_eligible_dict="0",
            train_role_dict="review_exclude",
            negative_chain_dict="期货/衍生品/套保套利咨询默认不纳入证券、基金与财富管理投顾主样本",
            rule_id_dict="R2_FUTURES_BOUNDARY",
        )
        return set_common_hits(result, row, [], HARD_NEG_FUTURES_TERMS)

    if contains_any(text, HARD_NEG_SALES_TERMS) and not positive_chain:
        if contains_any(text, ADVISOR_WEAK_POS_TERMS):
            result = Result(
                advisor_type_dict="R_boundary_review",
                confidence_dict="medium",
                review_flag="1",
                train_eligible_dict="0",
                train_role_dict="review_exclude",
                negative_chain_dict="仅客户开发/产品销售/开户转化/销售指标，无客户风险识别、资产配置、投资建议或投后服务链条",
                rule_id_dict="R3_SALES_MIXED_REVIEW",
            )
        else:
            result = Result(
                train_role_dict="hard_negative",
                negative_chain_dict="仅客户开发/产品销售/开户转化/销售指标，无客户风险识别、资产配置、投资建议或投后服务链条",
                rule_id_dict="R3_SALES_LOCK_HIGH_NEG",
            )
        return set_common_hits(result, row, ADVISOR_WEAK_POS_TERMS, HARD_NEG_SALES_TERMS)

    if contains_any(text, HARD_NEG_RESEARCH_TERMS) and not contains_any(text, ["投顾组合", "基金投顾策略", "客户资产配置", "适当性", "投后服务"]):
        result = Result(
            train_role_dict="hard_negative",
            negative_chain_dict="仅卖方研究/行业研究/研究报告/机构路演，无客户画像、适当性、资产配置或投顾组合服务对象",
            rule_id_dict="R4_RESEARCH_LOCK",
        )
        return set_common_hits(result, row, [], HARD_NEG_RESEARCH_TERMS)

    if contains_any(text, HARD_NEG_IT_CRM_TERMS) and not robo_module_chain(text):
        if "智能投顾" in text:
            result = Result(
                advisor_type_dict="R_boundary_review",
                confidence_dict="medium",
                review_flag="1",
                train_eligible_dict="0",
                train_role_dict="review_exclude",
                negative_chain_dict="普通IT/CRM/用户增长/智能推荐，系统对象为营销或运营，无投顾平台、风险测评、组合生成、资产配置或投顾留痕职责",
                rule_id_dict="R5_ROBO_ENUM_REVIEW",
            )
        else:
            result = Result(
                train_role_dict="hard_negative",
                negative_chain_dict="普通IT/CRM/用户增长/智能推荐，系统对象为营销或运营，无投顾平台、风险测评、组合生成、资产配置或投顾留痕职责",
                rule_id_dict="R5_IT_CRM_LOCK",
            )
        return set_common_hits(result, row, ROBO_ADVISOR_TERMS, HARD_NEG_IT_CRM_TERMS)

    if contains_any(text, HARD_NEG_FUND_OPS_TERMS) and not managed_fund_chain(text):
        result = Result(
            train_role_dict="hard_negative",
            negative_chain_dict="普通基金运营/TA/清算/估值/申赎处理，无管理型基金投顾、客户授权账户或投顾组合调仓对象",
            rule_id_dict="R6_FUND_OPS_LOCK",
        )
        return set_common_hits(result, row, [], HARD_NEG_FUND_OPS_TERMS)

    if contains_any(text, HARD_NEG_CONTENT_TERMS) and not contains_any(text, ["风险揭示", "组合解释", "投后陪伴", "投顾服务", "客户资产配置"]):
        review = contains_any(text, ["证券投资顾问资格", "投资顾问"])
        result = Result(
            advisor_type_dict="R_boundary_review" if review else "N_non_adviser",
            confidence_dict="medium",
            review_flag="1" if review else "0",
            train_eligible_dict="0" if review else "1",
            train_role_dict="review_exclude" if review else "hard_negative",
            negative_chain_dict="普通投教/内容/课程/讲师，无投资建议、组合解释、风险揭示或投顾持续服务职责",
            rule_id_dict="R7_CONTENT_LOCK",
        )
        return set_common_hits(result, row, ["证券投资顾问资格", "投资顾问"], HARD_NEG_CONTENT_TERMS)

    if positive_chain:
        sales_mixed = contains_any(text, HARD_NEG_SALES_TERMS) or match_a_audit == "A_INVESTMENT_ADVISOR_WITH_D_NEG_REVIEW"
        result = Result(
            advisor_job_dict="1",
            advisor_scope_dict="core_frontline",
            advisor_type_dict="A_frontline_client_adviser",
            function_tags_dict="HardTask;SoftTask;ComplianceTask",
            confidence_dict="medium" if sales_mixed else "high",
            review_flag="1" if sales_mixed else "0",
            train_eligible_dict="0" if sales_mixed else "1",
            train_role_dict="review_exclude" if sales_mixed else "gold_positive",
            key_evidence_dict="识别客户风险/目标/资产状况 + 提供投资建议/资产配置/组合服务 + 支持客户投后服务或风险解释",
            rule_id_dict="R8_FRONTLINE_SALES_MIXED_REVIEW" if sales_mixed else "R8_FRONTLINE_HIGH_POS",
        )
        return set_common_hits(result, row, full_pos_hits, HARD_NEG_SALES_TERMS if sales_mixed else [])

    if contains_any(text, SUPPORT_STRATEGY_TERMS):
        if strategy_object_chain(text):
            result = Result(
                advisor_job_dict="1",
                advisor_scope_dict="chain_support",
                advisor_type_dict="B_portfolio_strategy_advice",
                function_tags_dict="HardTask;InterfaceTask",
                train_role_dict="gold_positive",
                key_evidence_dict="形成投顾组合/基金投顾策略/资产配置方案 + 输出投资建议依据或客户服务支持",
                rule_id_dict="R9_STRATEGY_HIGH_POS",
            )
            return set_common_hits(result, row, SUPPORT_STRATEGY_TERMS + STRATEGY_OBJECT_TERMS, [])
        if contains_any(text, ORDINARY_RESEARCH_ONLY_TERMS):
            result = Result(
                train_role_dict="hard_negative",
                negative_chain_dict="仅基金研究/基金池/产品准入，无投顾组合或客户投资建议对象",
                rule_id_dict="R9_FUND_RESEARCH_HARD_NEG",
            )
            return set_common_hits(result, row, [], ORDINARY_RESEARCH_ONLY_TERMS)

    if contains_any(text, ROBO_PLATFORM_TERMS):
        if contains_any(text, ROBO_MODULE_TERMS):
            result = Result(
                advisor_job_dict="1",
                advisor_scope_dict="chain_support",
                advisor_type_dict="C_robo_adviser_system_support",
                function_tags_dict="HardTask;InterfaceTask;ComplianceTask",
                train_role_dict="gold_positive",
                key_evidence_dict="建设/运营智能投顾或投顾平台 + 支持风险测评、组合生成、资产配置、再平衡或投顾留痕",
                rule_id_dict="R10_ROBO_HIGH_POS",
            )
            return set_common_hits(result, row, ROBO_PLATFORM_TERMS + ROBO_MODULE_TERMS, [])
        if contains_any(text, CRM_HARD_NEG_CHAIN):
            result = Result(
                train_role_dict="hard_negative",
                negative_chain_dict="客户画像服务于营销触达或产品销售，不服务风险测评、组合生成、资产配置或投顾留痕",
                rule_id_dict="R10_CRM_HARD_NEG",
            )
            return set_common_hits(result, row, [], CRM_HARD_NEG_CHAIN)

    if contains_any(text, COMPLIANCE_SERVICE_TERMS):
        if contains_any(text, COMPLIANCE_OBJECT_TERMS):
            result = Result(
                advisor_job_dict="1",
                advisor_scope_dict="chain_support",
                advisor_type_dict="D_suitability_compliance_service",
                function_tags_dict="ComplianceTask",
                train_role_dict="gold_positive",
                key_evidence_dict="管理投顾业务适当性/风险揭示/协议/留痕/回访 + 支持投顾服务合规运行",
                rule_id_dict="R11_COMPLIANCE_HIGH_POS",
            )
            return set_common_hits(result, row, COMPLIANCE_SERVICE_TERMS + COMPLIANCE_OBJECT_TERMS, [])
        result = Result(
            train_role_dict="hard_negative",
            negative_chain_dict="普通合规/回访/投诉/合同审核，无投顾业务、投资建议或投顾服务留痕对象",
            rule_id_dict="R11_COMPLIANCE_HARD_NEG",
        )
        return set_common_hits(result, row, [], COMPLIANCE_SERVICE_TERMS)

    if managed_fund_chain(text):
        result = Result(
            advisor_job_dict="1",
            advisor_scope_dict="chain_support",
            advisor_type_dict="E_managed_fund_advisory_ops",
            function_tags_dict="OpsTask;ComplianceTask",
            train_role_dict="gold_positive",
            key_evidence_dict="支持客户授权账户或管理型基金投顾 + 执行投顾组合调仓、再平衡、申赎转换或披露",
            rule_id_dict="R12_MANAGED_FUND_HIGH_POS",
        )
        return set_common_hits(result, row, MANAGED_FUND_OPS_TERMS, [])

    if contains_any(text, MANAGEMENT_TERMS):
        if contains_any(text, MANAGEMENT_OBJECT_TERMS):
            result = Result(
                advisor_job_dict="1",
                advisor_scope_dict="chain_support",
                advisor_type_dict="F_advisory_business_management",
                function_tags_dict="ManagementTask",
                train_role_dict="gold_positive",
                key_evidence_dict="管理投顾业务/投顾团队/投顾服务质量 + 推动投顾服务体系或资产配置服务落地",
                rule_id_dict="R13_MANAGEMENT_HIGH_POS",
            )
            return set_common_hits(result, row, MANAGEMENT_TERMS + MANAGEMENT_OBJECT_TERMS, [])
        if contains_any(text, SALES_MANAGEMENT_TERMS):
            result = Result(
                train_role_dict="hard_negative",
                negative_chain_dict="仅销售团队管理或渠道管理，无投顾业务、资产配置、投资建议或服务质量管理对象",
                rule_id_dict="R13_SALES_MANAGEMENT_HARD_NEG",
            )
            return set_common_hits(result, row, [], SALES_MANAGEMENT_TERMS)

    if contains_any(text, ASSISTANT_TERMS):
        if contains_any(text, ASSISTANT_POS_TERMS):
            result = Result(
                advisor_job_dict="1",
                advisor_scope_dict="core_frontline",
                advisor_type_dict="A_frontline_client_adviser",
                confidence_dict="medium",
                review_flag="1",
                train_eligible_dict="0",
                train_role_dict="review_exclude",
                rule_id_dict="R14_ASSISTANT_POS_REVIEW",
                key_evidence_dict="助理岗位参与投顾任务链，需人工复核后使用",
            )
            return set_common_hits(result, row, ASSISTANT_TERMS + ASSISTANT_POS_TERMS, [])
        result = Result(
            advisor_type_dict="R_boundary_review",
            confidence_dict="medium",
            review_flag="1",
            train_eligible_dict="0",
            train_role_dict="review_exclude",
            negative_chain_dict="助理岗位仅做资料整理、客户答疑、客户活动、产品安装或销售辅助，无投顾任务链条",
            rule_id_dict="R14_ASSISTANT_REVIEW_NEG",
        )
        return set_common_hits(result, row, ASSISTANT_TERMS, [])

    if contains_any(text, ADVISORY_SIGNING_TERMS) and not contains_any(text, ADVISORY_SIGNING_POS_TERMS):
        result = Result(
            advisor_type_dict="R_boundary_review",
            confidence_dict="medium",
            review_flag="1",
            train_eligible_dict="0",
            train_role_dict="review_exclude",
            negative_chain_dict="仅投顾产品推广或协议签约，无风险揭示、适当性、建议留痕或持续服务职责",
            rule_id_dict="R15_ADVISORY_PRODUCT_SIGNING_REVIEW",
        )
        return set_common_hits(result, row, ADVISORY_SIGNING_TERMS, [])

    if contains_any(text, WEAK_SIGNAL_TERMS) or match_a_audit in {"A_ONLY_INVESTMENT_ADVISOR_EMPTY_DESC", "A_ASSISTANT_REVIEW", "A_INVESTMENT_ADVISOR_WITH_D_NEG_REVIEW"}:
        result = Result(
            advisor_type_dict="R_boundary_review",
            confidence_dict="medium" if contains_any(text, ["投资顾问", "财富管理", "资产配置"]) else "low",
            review_flag="1",
            train_eligible_dict="0",
            train_role_dict="review_exclude",
            negative_chain_dict="仅命中财富/理财/高净值客户/资产配置等弱信号，未形成客户风险识别、资产配置、投资建议或投后服务链条",
            rule_id_dict="R16_WEAK_SIGNAL_REVIEW",
        )
        return set_common_hits(result, row, WEAK_SIGNAL_TERMS + STRONG_ADVISOR_TITLE_TERMS, split_terms(row.get(MATCH_D_COL, "")))

    result = Result(negative_chain_dict="未见证券、基金、财富管理投顾任务链", rule_id_dict="R17_DEFAULT_NEGATIVE")
    return set_common_hits(result, row, [], [])


def enforce_quality_contract(result: Result) -> Result:
    if result.confidence_dict in {"medium", "low"}:
        result.review_flag = "1"
        result.train_eligible_dict = "0"
        result.train_role_dict = "review_exclude"
    return result


def output_paths(input_path: Path, output: Path | None, summary: Path | None) -> tuple[Path, Path]:
    classified = output or input_path.with_name(input_path.stem + "_dict_classified.csv")
    summary_path = summary or input_path.with_name("advisor_dict_classifier_audit_summary.csv")
    return classified, summary_path


def process(input_path: Path, output_path: Path, summary_path: Path) -> dict[str, object]:
    encoding = detect_encoding(input_path)
    header, duckdb_rows = validate_input_with_duckdb(input_path, encoding)
    output_fields = header + [field for field in DICT_FIELDS if field not in header]
    summary_counter: Counter[tuple[str, str, str, str, str, str, str]] = Counter()
    row_count = 0
    rule_counter: Counter[str] = Counter()
    confidence_counter: Counter[str] = Counter()
    job_counter: Counter[str] = Counter()
    review_counter: Counter[str] = Counter()
    train_role_counter: Counter[str] = Counter()
    failures: defaultdict[str, int] = defaultdict(int)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding=encoding, newline="") as src, output_path.open("w", encoding="utf-8-sig", newline="") as dst:
        reader = csv.DictReader(src)
        writer = csv.DictWriter(dst, fieldnames=output_fields, extrasaction="ignore")
        writer.writeheader()
        for row in reader:
            result = enforce_quality_contract(classify_row(row))
            result_dict = result.as_dict()
            row_count += 1
            merged = {field: row.get(field, "") for field in header}
            merged.update(result_dict)
            writer.writerow(merged)

            key = (
                row.get("sample_pool", ""),
                row.get("advisor_recall_level", ""),
                result.advisor_job_dict,
                result.confidence_dict,
                result.review_flag,
                result.train_role_dict,
                result.rule_id_dict,
            )
            summary_counter[key] += 1
            rule_counter[result.rule_id_dict] += 1
            confidence_counter[result.confidence_dict] += 1
            job_counter[result.advisor_job_dict] += 1
            review_counter[result.review_flag] += 1
            train_role_counter[result.train_role_dict] += 1

            if result.classifier_version != CLASSIFIER_VERSION:
                failures["bad_classifier_version"] += 1
            if result.confidence_dict in {"medium", "low"} and not (result.review_flag == "1" and result.train_eligible_dict == "0"):
                failures["medium_low_contract"] += 1
            if result.confidence_dict == "high" and result.review_flag == "0" and result.advisor_job_dict == "1":
                if not result.quote_span_dict or not result.key_evidence_dict:
                    failures["high_positive_evidence"] += 1
            if result.confidence_dict == "high" and result.review_flag == "0" and result.advisor_job_dict == "0":
                if not result.negative_chain_dict:
                    failures["high_negative_chain"] += 1

    with summary_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for key, count in sorted(summary_counter.items()):
            writer.writerow(dict(zip(SUMMARY_FIELDS[:-1], key)) | {"count": count})

    summary_total = sum(summary_counter.values())
    return {
        "encoding": encoding,
        "duckdb_rows": duckdb_rows,
        "rows_written": row_count,
        "summary_rows": len(summary_counter),
        "summary_total": summary_total,
        "job_counts": dict(job_counter),
        "confidence_counts": dict(confidence_counter),
        "review_counts": dict(review_counter),
        "train_role_counts": dict(train_role_counter),
        "rule_counts": dict(rule_counter),
        "failures": dict(failures),
        "output": str(output_path),
        "summary": str(summary_path),
    }


def validate_written_output(input_path: Path, output_path: Path, summary_path: Path, expected_header: list[str], expected_rows: int) -> dict[str, int | bool]:
    with output_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        out_header = reader.fieldnames or []
        rows = list(reader)
    with summary_path.open("r", encoding="utf-8-sig", newline="") as f:
        summary_rows = list(csv.DictReader(f))
    summary_total = sum(int(row["count"]) for row in summary_rows)
    original_prefix_ok = out_header[: len(expected_header)] == expected_header
    added_fields_ok = out_header[len(expected_header) :] == [field for field in DICT_FIELDS if field not in expected_header]
    version_ok = all(row.get("classifier_version") == CLASSIFIER_VERSION for row in rows)
    return {
        "output_has_bom": output_path.read_bytes().startswith(b"\xef\xbb\xbf"),
        "summary_has_bom": summary_path.read_bytes().startswith(b"\xef\xbb\xbf"),
        "rows_readback": len(rows),
        "expected_rows": expected_rows,
        "row_count_ok": len(rows) == expected_rows,
        "original_prefix_ok": original_prefix_ok,
        "added_fields_ok": added_fields_ok,
        "version_ok": version_ok,
        "summary_nonempty": len(summary_rows) > 0,
        "summary_total": summary_total,
        "summary_total_ok": summary_total == expected_rows,
    }


def print_counts(label: str, counts: dict[str, int]) -> None:
    print(label + "=" + "; ".join(f"{key}:{counts[key]}" for key in sorted(counts)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify advisor recall sample part1 with a v0 DuckDB-backed dictionary classifier.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--summary", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = args.input
    if not input_path.exists():
        raise FileNotFoundError(input_path)
    output_path, summary_path = output_paths(input_path, args.output, args.summary)
    header = read_header(input_path, detect_encoding(input_path))
    stats = process(input_path, output_path, summary_path)
    validation = validate_written_output(input_path, output_path, summary_path, header, int(stats["duckdb_rows"]))

    print(f"input={input_path}")
    print(f"encoding={stats['encoding']}")
    print(f"duckdb_rows={stats['duckdb_rows']}")
    print(f"rows_written={stats['rows_written']}")
    print(f"output={output_path}")
    print(f"summary={summary_path}")
    print_counts("advisor_job_dict_counts", stats["job_counts"])
    print_counts("confidence_counts", stats["confidence_counts"])
    print_counts("review_flag_counts", stats["review_counts"])
    print_counts("train_role_counts", stats["train_role_counts"])
    print_counts("rule_id_counts", stats["rule_counts"])
    print(f"summary_groups={stats['summary_rows']}")
    print(f"summary_total={stats['summary_total']}")
    for key, value in validation.items():
        print(f"{key}={value}")
    if stats["failures"]:
        print(f"quality_failures={stats['failures']}")
        raise RuntimeError("Quality checks failed")
    failing_validation = {key: value for key, value in validation.items() if key.endswith("_ok") and not value}
    if failing_validation or not validation["summary_nonempty"] or not validation["output_has_bom"] or not validation["summary_has_bom"]:
        raise RuntimeError(f"Output validation failed: {failing_validation}")
    print("quality_checks=PASS")


if __name__ == "__main__":
    main()
