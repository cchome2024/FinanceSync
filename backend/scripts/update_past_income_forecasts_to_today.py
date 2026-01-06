#!/usr/bin/env python3
"""
将所有早于今天的预测性收入日期更新到今天

用法:
    poetry run python scripts/update_past_income_forecasts_to_today.py [options]
    
选项:
    --company-id <id>          只更新指定公司的记录
    --dry-run                   预览模式，不实际修改数据
    --force                     强制更新，合并重复记录（金额相加）
    
示例:
    # 预览模式，查看会更新哪些记录
    poetry run python scripts/update_past_income_forecasts_to_today.py --dry-run
    
    # 实际更新所有早于今天的预测性收入
    poetry run python scripts/update_past_income_forecasts_to_today.py
    
    # 只更新指定公司的记录
    poetry run python scripts/update_past_income_forecasts_to_today.py --company-id abc123
    
    # 强制更新，合并重复记录
    poetry run python scripts/update_past_income_forecasts_to_today.py --force
"""

import sys
import argparse
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from collections import defaultdict

# 添加项目根目录到路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import and_
from app.db import SessionLocal
from app.models.financial import IncomeForecast, Company


def update_past_income_forecasts_to_today(
    company_id: Optional[str] = None,
    dry_run: bool = False,
    force: bool = False,
) -> None:
    """将所有早于今天的预测性收入日期更新到今天"""
    session = SessionLocal()
    try:
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        
        # 构建查询条件：只查询早于今天的记录
        conditions = [IncomeForecast.cash_in_date < today]
        
        if company_id:
            # 验证公司是否存在
            company = session.query(Company).filter(Company.id == company_id).first()
            if not company:
                print(f"❌ 公司 ID {company_id} 不存在")
                sys.exit(1)
            conditions.append(IncomeForecast.company_id == company_id)
            print(f"📌 公司: {company.display_name} ({company.name})")
        
        # 查询符合条件的记录
        query = session.query(IncomeForecast).filter(and_(*conditions))
        records = query.all()
        
        if not records:
            print("ℹ️  没有找到早于今天的预测性收入记录")
            return
        
        print(f"\n📊 找到 {len(records)} 条早于今天的预测性收入记录")
        print(f"🎯 目标日期: {today}")
        print(f"📅 当前日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if dry_run:
            print("\n🔍 预览模式 - 以下记录将被更新:")
            print("-" * 100)
            
            # 按公司分组显示
            by_company = defaultdict(list)
            for record in records:
                company_name = record.company.display_name if record.company else 'N/A'
                by_company[company_name].append(record)
            
            total_amount = 0.0
            for company_name, company_records in by_company.items():
                print(f"\n🏢 公司: {company_name} ({len(company_records)} 条记录)")
                for record in company_records[:5]:  # 每个公司只显示前5条
                    print(f"  ID: {record.id}")
                    print(f"  当前日期: {record.cash_in_date} → 新日期: {today}")
                    print(f"  金额: {record.expected_amount:,.2f} {record.currency}")
                    print(f"  类型: {record.certainty.value}")
                    print(f"  分类: {record.category_label or record.category or 'N/A'}")
                    print(f"  描述: {record.description or 'N/A'}")
                    print("-" * 100)
                    total_amount += float(record.expected_amount)
                if len(company_records) > 5:
                    print(f"  ... 还有 {len(company_records) - 5} 条记录")
            
            print(f"\n💰 总金额: {total_amount:,.2f}")
            print("\n⚠️  这是预览模式，实际数据不会被修改")
            return
        
        # 检查唯一约束冲突并处理
        records_to_update = []
        records_to_delete = set()
        merged_records = {}  # 用于合并重复记录: key -> (record, amount_to_add)
        
        for record in records:
            # 检查是否存在相同的记录（除了日期不同）
            existing = session.query(IncomeForecast).filter(
                and_(
                    IncomeForecast.company_id == record.company_id,
                    IncomeForecast.cash_in_date == today,
                    IncomeForecast.expected_amount == record.expected_amount,
                    IncomeForecast.category_id == record.category_id,
                    IncomeForecast.description == record.description,
                    IncomeForecast.account_name == record.account_name,
                    IncomeForecast.certainty == record.certainty,
                    IncomeForecast.id != record.id,  # 排除自己
                )
            ).first()
            
            if existing:
                if force:
                    # 强制模式下，合并金额（将旧记录的金额加到已存在的记录上）
                    merge_key = (
                        record.company_id,
                        record.category_id,
                        record.description,
                        record.account_name,
                        record.certainty,
                    )
                    if merge_key not in merged_records:
                        merged_records[merge_key] = (existing, 0.0)
                    merged_records[merge_key] = (
                        merged_records[merge_key][0],
                        merged_records[merge_key][1] + float(record.expected_amount)
                    )
                    records_to_delete.add(record.id)
                    print(f"🔄 记录 {record.id} 将与已存在的记录 {existing.id} 合并")
                else:
                    # 非强制模式下，跳过这条记录
                    print(f"⚠️  记录 {record.id} 与已存在的记录 {existing.id} 冲突，跳过")
                    continue
            else:
                records_to_update.append(record)
        
        # 执行合并（强制模式下）
        if force and merged_records:
            for merge_key, (existing_record, amount_to_add) in merged_records.items():
                existing_record.expected_amount += amount_to_add
                print(f"✅ 合并记录 {existing_record.id}，增加金额 {amount_to_add:,.2f}")
        
        # 删除需要删除的记录
        if records_to_delete:
            deleted_count = session.query(IncomeForecast).filter(
                IncomeForecast.id.in_(records_to_delete)
            ).delete(synchronize_session=False)
            print(f"🗑️  删除了 {deleted_count} 条重复记录")
        
        # 执行更新
        updated_count = 0
        for record in records_to_update:
            old_date = record.cash_in_date
            record.cash_in_date = today
            updated_count += 1
        
        session.commit()
        print(f"\n✅ 成功更新 {updated_count} 条记录的日期到 {today}")
        
        if force and merged_records:
            print(f"✅ 合并了 {len(merged_records)} 组重复记录")
        
    except Exception as e:
        session.rollback()
        print(f"❌ 更新失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="将所有早于今天的预测性收入日期更新到今天",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        "--company-id",
        type=str,
        help="只更新指定公司的记录",
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，不实际修改数据",
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制更新，合并重复记录（金额相加）",
    )
    
    args = parser.parse_args()
    
    # 执行更新
    update_past_income_forecasts_to_today(
        company_id=args.company_id,
        dry_run=args.dry_run,
        force=args.force,
    )

