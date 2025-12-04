#!/usr/bin/env python3
"""
调整预测收入表日期的工具脚本

用法:
    poetry run python scripts/adjust_income_forecast_date.py <target_date> [options]
    
参数:
    target_date     目标日期 (格式: YYYY-MM-DD)
    
选项:
    --company-id <id>          只调整指定公司的记录
    --from-date <date>         只调整指定日期之后的记录 (格式: YYYY-MM-DD)
    --to-date <date>           只调整指定日期之前的记录 (格式: YYYY-MM-DD)
    --category <category>      只调整指定分类的记录
    --dry-run                   预览模式，不实际修改数据
    --force                     强制更新，即使可能违反唯一约束
    
示例:
    # 将所有预测收入日期调整为 2025-01-01
    poetry run python scripts/adjust_income_forecast_date.py 2025-01-01
    
    # 只调整指定公司的记录
    poetry run python scripts/adjust_income_forecast_date.py 2025-01-01 --company-id abc123
    
    # 只调整 2024-12-01 之后的记录
    poetry run python scripts/adjust_income_forecast_date.py 2025-01-01 --from-date 2024-12-01
    
    # 预览模式，查看会修改哪些记录
    poetry run python scripts/adjust_income_forecast_date.py 2025-01-01 --dry-run
"""

import sys
import argparse
from datetime import date, datetime
from pathlib import Path
from typing import Optional

# 添加项目根目录到路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import and_, or_
from app.db import SessionLocal
from app.models.financial import IncomeForecast, Company


def parse_date(date_str: str) -> date:
    """解析日期字符串"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        print(f"❌ 无效的日期格式: {date_str}，请使用 YYYY-MM-DD 格式")
        sys.exit(1)


def adjust_income_forecast_dates(
    target_date: date,
    company_id: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    category: Optional[str] = None,
    dry_run: bool = False,
    force: bool = False,
) -> None:
    """调整预测收入表的日期"""
    session = SessionLocal()
    try:
        # 构建查询条件
        conditions = []
        
        if company_id:
            # 验证公司是否存在
            company = session.query(Company).filter(Company.id == company_id).first()
            if not company:
                print(f"❌ 公司 ID {company_id} 不存在")
                sys.exit(1)
            conditions.append(IncomeForecast.company_id == company_id)
            print(f"📌 公司: {company.display_name} ({company.name})")
        
        if from_date:
            conditions.append(IncomeForecast.cash_in_date >= from_date)
            print(f"📅 起始日期: {from_date}")
        
        if to_date:
            conditions.append(IncomeForecast.cash_in_date <= to_date)
            print(f"📅 结束日期: {to_date}")
        
        if category:
            conditions.append(
                or_(
                    IncomeForecast.category == category,
                    IncomeForecast.category_label == category,
                    IncomeForecast.category_path_text.like(f"%{category}%"),
                )
            )
            print(f"🏷️  分类: {category}")
        
        # 查询符合条件的记录
        query = session.query(IncomeForecast)
        if conditions:
            query = query.filter(and_(*conditions))
        
        records = query.all()
        
        if not records:
            print("ℹ️  没有找到符合条件的记录")
            return
        
        print(f"\n📊 找到 {len(records)} 条符合条件的记录")
        print(f"🎯 目标日期: {target_date}")
        
        if dry_run:
            print("\n🔍 预览模式 - 以下记录将被更新:")
            print("-" * 100)
            for record in records[:10]:  # 只显示前10条
                print(f"  ID: {record.id}")
                print(f"  公司: {record.company.display_name if record.company else 'N/A'}")
                print(f"  当前日期: {record.cash_in_date} → 新日期: {target_date}")
                print(f"  金额: {record.expected_amount} {record.currency}")
                print(f"  分类: {record.category_label or record.category or 'N/A'}")
                print(f"  描述: {record.description or 'N/A'}")
                print("-" * 100)
            if len(records) > 10:
                print(f"  ... 还有 {len(records) - 10} 条记录")
            print("\n⚠️  这是预览模式，实际数据不会被修改")
            return
        
        # 检查唯一约束冲突
        conflicts = []
        records_to_update = []
        records_to_delete = set()  # 记录需要删除的ID
        
        for record in records:
            # 检查是否存在相同的记录（除了日期不同）
            existing = session.query(IncomeForecast).filter(
                and_(
                    IncomeForecast.company_id == record.company_id,
                    IncomeForecast.cash_in_date == target_date,
                    IncomeForecast.expected_amount == record.expected_amount,
                    IncomeForecast.category_id == record.category_id,
                    IncomeForecast.description == record.description,
                    IncomeForecast.account_name == record.account_name,
                    IncomeForecast.id != record.id,  # 排除自己
                )
            ).first()
            
            if existing:
                conflicts.append({
                    "record": record,
                    "existing": existing,
                })
                if force:
                    # 强制模式下，删除已存在的记录
                    records_to_delete.add(existing.id)
                else:
                    # 非强制模式下，跳过这条记录
                    continue
            
            records_to_update.append(record)
        
        if conflicts and not force:
            print(f"\n⚠️  发现 {len(conflicts)} 条记录可能违反唯一约束:")
            for conflict in conflicts[:5]:  # 只显示前5个冲突
                record = conflict["record"]
                existing = conflict["existing"]
                print(f"  记录 ID: {record.id}")
                print(f"    当前日期: {record.cash_in_date}")
                print(f"    与已存在的记录 ID: {existing.id} 冲突")
                print(f"    (日期: {existing.cash_in_date}, 金额: {existing.expected_amount})")
            
            if len(conflicts) > 5:
                print(f"  ... 还有 {len(conflicts) - 5} 个冲突")
            
            print("\n💡 提示: 使用 --force 参数可以强制更新（会删除冲突的重复记录）")
            sys.exit(1)
        
        # 强制模式下，先删除冲突的记录
        if force and records_to_delete:
            deleted_count = session.query(IncomeForecast).filter(
                IncomeForecast.id.in_(records_to_delete)
            ).delete(synchronize_session=False)
            print(f"🗑️  强制模式下删除了 {deleted_count} 条冲突记录")
        
        # 执行更新
        updated_count = 0
        for record in records_to_update:
            old_date = record.cash_in_date
            record.cash_in_date = target_date
            updated_count += 1
        
        session.commit()
        print(f"\n✅ 成功更新 {updated_count} 条记录的日期到 {target_date}")
        
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
        description="调整预测收入表的日期",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        "target_date",
        type=str,
        help="目标日期 (格式: YYYY-MM-DD)",
    )
    
    parser.add_argument(
        "--company-id",
        type=str,
        help="只调整指定公司的记录",
    )
    
    parser.add_argument(
        "--from-date",
        type=str,
        help="只调整指定日期之后的记录 (格式: YYYY-MM-DD)",
    )
    
    parser.add_argument(
        "--to-date",
        type=str,
        help="只调整指定日期之前的记录 (格式: YYYY-MM-DD)",
    )
    
    parser.add_argument(
        "--category",
        type=str,
        help="只调整指定分类的记录",
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，不实际修改数据",
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制更新，即使可能违反唯一约束",
    )
    
    args = parser.parse_args()
    
    # 解析日期
    target_date = parse_date(args.target_date)
    from_date = parse_date(args.from_date) if args.from_date else None
    to_date = parse_date(args.to_date) if args.to_date else None
    
    # 执行调整
    adjust_income_forecast_dates(
        target_date=target_date,
        company_id=args.company_id,
        from_date=from_date,
        to_date=to_date,
        category=args.category,
        dry_run=args.dry_run,
        force=args.force,
    )

