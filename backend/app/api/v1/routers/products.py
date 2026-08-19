"""Product master-data endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.db.session import get_db
from app.models import Product
from app.schemas import Page, ProductCreate, ProductRead, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=Page[ProductRead])
def list_products(
    db: Session = Depends(get_db),
    category: str | None = Query(default=None),
    active: bool | None = Query(default=None),
    search: str | None = Query(default=None, description="Matches SKU or name"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Page[ProductRead]:
    statement = select(Product)
    if category:
        statement = statement.where(Product.category == category)
    if active is not None:
        statement = statement.where(Product.active.is_(active))
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            (Product.sku.ilike(pattern)) | (Product.name.ilike(pattern))
        )

    total = db.execute(select(func.count()).select_from(statement.subquery())).scalar_one()
    rows = db.execute(
        statement.order_by(Product.sku).limit(limit).offset(offset)
    ).scalars().all()

    return Page(items=list(rows), total=total, limit=limit, offset=offset)


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: int, db: Session = Depends(get_db)) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError(f"Product {product_id} not found.", details={"product_id": product_id})
    return product


@router.post("", response_model=ProductRead, status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)) -> Product:
    product = Product(**payload.model_dump())
    db.add(product)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            f"A product with SKU {payload.sku!r} already exists.", details={"sku": payload.sku}
        ) from exc
    db.refresh(product)
    return product


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db)) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError(f"Product {product_id} not found.", details={"product_id": product_id})

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=204, response_model=None)
def deactivate_product(product_id: int, db: Session = Depends(get_db)) -> None:
    """Soft-delete: products are deactivated, never hard-deleted, to preserve history."""
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError(f"Product {product_id} not found.", details={"product_id": product_id})
    product.active = False
    db.commit()
