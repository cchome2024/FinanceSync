#!/usr/bin/env python3
"""
合并所有公司数据到一个公司

用法:
    poetry run python scripts/merge_all_companies.py [options]
    
选项:
    --target-company-id <id>     目标公司ID（如果不指定，会使用第一个有数据的公司或创建新公司）
    --target-company-name <name> 目标公司名称（如果不指定，使用"默认公司"）
    --dry-run                     预览模式，不实际修改数据
    --force                       强制合并，即使可能丢失数据
    
示例:
    # 预览模式，查看会合并哪些数据
    poetry run python scripts/merge_all_companies.py --dry-run
    
    # 合并所有公司到指定公司
    poetry run python scripts/merge_all_companies.py --target-company-id abc123
    
    # 合并所有公司到新创建的公司
    poetry run python scripts/merge_all_companies.py --target-company-name "我的公司"
"""

import sys
import argparse
from pathlib import Path
from typing import Optional

# 添加项目根目录到路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import func
from app.db import SessionLocal
from app.models.financial import (
    Company,
    AccountBalance,
    RevenueDetail,
    ExpenseRecord,
    IncomeForecast,
    ExpenseForecast,
)


def merge_all_companies(
    target_company_id: Optional[str] = None,
    target_company_name: Optional[str] = None,
    dry_run: bool = False,
    force: bool = False,
) -> None:
    """合并所有公司数据到一个公司"""
    session = SessionLocal()
    try:
        # 获取所有公司
        all_companies = session.query(Company).all()
        
        if not all_companies:
            print("ℹ️  数据库中没有公司")
            return
        
        print(f"\n📊 找到 {len(all_companies)} 个公司:")
        for company in all_companies:
            # 统计每个公司的数据量
            balance_count = session.query(AccountBalance).filter_by(company_id=company.id).count()
            revenue_count = session.query(RevenueDetail).filter_by(company_id=company.id).count()
            expense_count = session.query(ExpenseRecord).filter_by(company_id=company.id).count()
            income_forecast_count = session.query(IncomeForecast).filter_by(company_id=company.id).count()
            expense_forecast_count = session.query(ExpenseForecast).filter_by(company_id=company.id).count()
            
            print(f"  - {company.display_name or company.name} (ID: {company.id})")
            print(f"    余额: {balance_count}, 收入: {revenue_count}, 支出: {expense_count}")
            print(f"    预测收入: {income_forecast_count}, 预测支出: {expense_forecast_count}")
        
        # 确定目标公司
        target_company = None
        if target_company_id:
            target_company = session.query(Company).filter_by(id=target_company_id).first()
            if not target_company:
                print(f"❌ 目标公司 ID {target_company_id} 不存在")
                sys.exit(1)
            print(f"\n🎯 使用指定的目标公司: {target_company.display_name or target_company.name} (ID: {target_company.id})")
        else:
            # 优先选择有数据的公司
            for company in all_companies:
                has_data = (
                    session.query(AccountBalance).filter_by(company_id=company.id).count() > 0 or
                    session.query(RevenueDetail).filter_by(company_id=company.id).count() > 0 or
                    session.query(ExpenseRecord).filter_by(company_id=company.id).count() > 0 or
                    session.query(IncomeForecast).filter_by(company_id=company.id).count() > 0 or
                    session.query(ExpenseForecast).filter_by(company_id=company.id).count() > 0
                )
                if has_data:
                    target_company = company
                    print(f"\n🎯 选择有数据的公司作为目标: {target_company.display_name or target_company.name} (ID: {target_company.id})")
                    break
            
            # 如果没有找到有数据的公司，创建新公司
            if not target_company:
                target_company_name = target_company_name or "默认公司"
                target_company = Company(
                    name="default-company",
                    display_name=target_company_name,
                )
                if not dry_run:
                    session.add(target_company)
                    session.flush()
                print(f"\n🎯 创建新公司作为目标: {target_company_name} (ID: {target_company.id})")
        
        # 需要合并的公司（排除目标公司）
        companies_to_merge = [c for c in all_companies if c.id != target_company.id]
        
        if not companies_to_merge:
            print("\n✅ 只有一个公司，无需合并")
            return
        
        print(f"\n📋 需要合并 {len(companies_to_merge)} 个公司到目标公司")
        
        # 统计需要迁移的数据
        total_migrations = {
            'balances': 0,
            'revenues': 0,
            'expenses': 0,
            'income_forecasts': 0,
            'expense_forecasts': 0,
        }
        
        for company in companies_to_merge:
            balance_count = session.query(AccountBalance).filter_by(company_id=company.id).count()
            revenue_count = session.query(RevenueDetail).filter_by(company_id=company.id).count()
            expense_count = session.query(ExpenseRecord).filter_by(company_id=company.id).count()
            income_forecast_count = session.query(IncomeForecast).filter_by(company_id=company.id).count()
            expense_forecast_count = session.query(ExpenseForecast).filter_by(company_id=company.id).count()
            
            total_migrations['balances'] += balance_count
            total_migrations['revenues'] += revenue_count
            total_migrations['expenses'] += expense_count
            total_migrations['income_forecasts'] += income_forecast_count
            total_migrations['expense_forecasts'] += expense_forecast_count
            
            print(f"\n  {company.display_name or company.name}:")
            print(f"    余额: {balance_count}, 收入: {revenue_count}, 支出: {expense_count}")
            print(f"    预测收入: {income_forecast_count}, 预测支出: {expense_forecast_count}")
        
        print(f"\n📊 总计需要迁移:")
        print(f"    余额: {total_migrations['balances']}")
        print(f"    收入: {total_migrations['revenues']}")
        print(f"    支出: {total_migrations['expenses']}")
        print(f"    预测收入: {total_migrations['income_forecasts']}")
        print(f"    预测支出: {total_migrations['expense_forecasts']}")
        
        if dry_run:
            print("\n⚠️  这是预览模式，实际数据不会被修改")
            return
        
        # 执行合并
        print("\n🔄 开始合并数据...")
        
        for company in companies_to_merge:
            print(f"\n  处理公司: {company.display_name or company.name}")
            
            # 迁移余额（处理唯一约束：company_id + reported_at）
            balances = session.query(AccountBalance).filter_by(company_id=company.id).all()
            balance_migrated = 0
            balance_skipped = 0
            for balance in balances:
                # 检查目标公司是否已有相同日期的余额记录
                existing = session.query(AccountBalance).filter_by(
                    company_id=target_company.id,
                    reported_at=balance.reported_at
                ).first()
                if existing:
                    # 如果已存在，保留目标公司的记录（或合并，这里选择保留目标公司）
                    balance_skipped += 1
                    session.delete(balance)
                else:
                    balance.company_id = target_company.id
                    balance_migrated += 1
            if balance_migrated > 0 or balance_skipped > 0:
                print(f"    ✅ 迁移了 {balance_migrated} 条余额记录，跳过了 {balance_skipped} 条重复记录")
            
            # 迁移收入（处理唯一约束）
            revenues = session.query(RevenueDetail).filter_by(company_id=company.id).all()
            revenue_migrated = 0
            revenue_skipped = 0
            for revenue in revenues:
                existing = session.query(RevenueDetail).filter_by(
                    company_id=target_company.id,
                    occurred_on=revenue.occurred_on,
                    amount=revenue.amount,
                    category_id=revenue.category_id,
                    description=revenue.description,
                    account_name=revenue.account_name,
                ).first()
                if existing:
                    revenue_skipped += 1
                    session.delete(revenue)
                else:
                    revenue.company_id = target_company.id
                    revenue_migrated += 1
            if revenue_migrated > 0 or revenue_skipped > 0:
                print(f"    ✅ 迁移了 {revenue_migrated} 条收入记录，跳过了 {revenue_skipped} 条重复记录")
            
            # 迁移支出（没有唯一约束，直接更新）
            expense_count = session.query(ExpenseRecord).filter_by(company_id=company.id).update(
                {"company_id": target_company.id}
            )
            if expense_count > 0:
                print(f"    ✅ 迁移了 {expense_count} 条支出记录")
            
            # 迁移预测收入（处理唯一约束）
            income_forecasts = session.query(IncomeForecast).filter_by(company_id=company.id).all()
            income_forecast_migrated = 0
            income_forecast_skipped = 0
            for forecast in income_forecasts:
                existing = session.query(IncomeForecast).filter_by(
                    company_id=target_company.id,
                    cash_in_date=forecast.cash_in_date,
                    expected_amount=forecast.expected_amount,
                    category_id=forecast.category_id,
                    description=forecast.description,
                    account_name=forecast.account_name,
                ).first()
                if existing:
                    income_forecast_skipped += 1
                    session.delete(forecast)
                else:
                    forecast.company_id = target_company.id
                    income_forecast_migrated += 1
            if income_forecast_migrated > 0 or income_forecast_skipped > 0:
                print(f"    ✅ 迁移了 {income_forecast_migrated} 条预测收入记录，跳过了 {income_forecast_skipped} 条重复记录")
            
            # 迁移预测支出（处理唯一约束）
            expense_forecasts = session.query(ExpenseForecast).filter_by(company_id=company.id).all()
            expense_forecast_migrated = 0
            expense_forecast_skipped = 0
            for forecast in expense_forecasts:
                existing = session.query(ExpenseForecast).filter_by(
                    company_id=target_company.id,
                    cash_out_date=forecast.cash_out_date,
                    expected_amount=forecast.expected_amount,
                    category_id=forecast.category_id,
                    description=forecast.description,
                    account_name=forecast.account_name,
                ).first()
                if existing:
                    expense_forecast_skipped += 1
                    session.delete(forecast)
                else:
                    forecast.company_id = target_company.id
                    expense_forecast_migrated += 1
            if expense_forecast_migrated > 0 or expense_forecast_skipped > 0:
                print(f"    ✅ 迁移了 {expense_forecast_migrated} 条预测支出记录，跳过了 {expense_forecast_skipped} 条重复记录")
            
            # 删除空公司（可选）
            if force:
                session.delete(company)
                print(f"    🗑️  删除了空公司")
        
        session.commit()
        print(f"\n✅ 成功合并所有公司数据到: {target_company.display_name or target_company.name} (ID: {target_company.id})")
        
        # 验证结果
        final_companies = session.query(Company).all()
        print(f"\n📊 合并后剩余 {len(final_companies)} 个公司:")
        for company in final_companies:
            balance_count = session.query(AccountBalance).filter_by(company_id=company.id).count()
            revenue_count = session.query(RevenueDetail).filter_by(company_id=company.id).count()
            expense_count = session.query(ExpenseRecord).filter_by(company_id=company.id).count()
            income_forecast_count = session.query(IncomeForecast).filter_by(company_id=company.id).count()
            expense_forecast_count = session.query(ExpenseForecast).filter_by(company_id=company.id).count()
            
            print(f"  - {company.display_name or company.name} (ID: {company.id})")
            print(f"    余额: {balance_count}, 收入: {revenue_count}, 支出: {expense_count}")
            print(f"    预测收入: {income_forecast_count}, 预测支出: {expense_forecast_count}")
        
    except Exception as e:
        session.rollback()
        print(f"❌ 合并失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="合并所有公司数据到一个公司",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        "--target-company-id",
        type=str,
        help="目标公司ID（如果不指定，会使用第一个有数据的公司或创建新公司）",
    )
    
    parser.add_argument(
        "--target-company-name",
        type=str,
        help="目标公司名称（如果不指定，使用'默认公司'）",
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，不实际修改数据",
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制合并，删除空公司",
    )
    
    args = parser.parse_args()
    
    # 执行合并
    merge_all_companies(
        target_company_id=args.target_company_id,
        target_company_name=args.target_company_name,
        dry_run=args.dry_run,
        force=args.force,
    )

