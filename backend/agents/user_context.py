from typing import Dict, Optional

def get_user_context(user_id: int) -> Optional[Dict]:
    """
    Mock of the User Context Aggregator that would typically query BigQuery/Firestore.
    It returns the profile data for a given user ID.
    """
    
    # Mock data base on user_id
    mock_profiles = {
        1: {
            "user_id": 1,
            "profession": "Diseñador Gráfico",
            "cnae_code": "7410",
            "cnae_description": "Actividades de diseño especializado",
            "location": "Madrid",
            "tax_regime": "Estimación directa",
            "deductible_categories": [
                "Software/Suscripciones (Adobe, Figma)",
                "Material de oficina",
                "Equipos informáticos",
                "Marketing/Publicidad",
                "Asesoría contable"
            ],
            "non_deductible_categories_alerts": [
                "Alimentación y supermercado",
                "Ropa (excepto EPIs específicos)",
                "Gastos personales"
            ]
        },
        2: {
            "user_id": 2,
            "profession": "Fontanero",
            "cnae_code": "4322",
            "cnae_description": "Fontanería, instalaciones de sistemas de calefacción y aire acondicionado",
            "location": "Valencia",
            "tax_regime": "Estimación objetiva (Módulos)",
            "deductible_categories": [
                "Herramientas y maquinaria",
                "Materiales de fontanería (tuberías, grifería)",
                "Ropa de trabajo (EPIs)",
                "Vehículo comercial y combustible",
                "Seguro de responsabilidad civil"
            ],
            "non_deductible_categories_alerts": [
                "Suscripciones a software de diseño",
                "Gastos de representación excesivos"
            ]
        }
    }
    
    # Return profile or default if not found
    return mock_profiles.get(user_id, {
        "user_id": user_id,
        "profession": "Autónomo General",
        "cnae_code": "Desconocido",
        "cnae_description": "Desconocido",
        "location": "España",
        "tax_regime": "Estimación directa",
        "deductible_categories": ["Gastos afectos a la actividad profesional"],
        "non_deductible_categories_alerts": ["Gastos personales no justificados"]
    })

def validate_expense_against_profile(expense_concept: str, profile: Dict) -> bool:
    """
    A simple rule-based fallback if the LLM is not used. 
    (In this phase, we will let the LLM do the actual validation).
    """
    pass
