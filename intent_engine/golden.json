[
 {
  "question": "Which B2B Dealer in Gujarat generated the highest gross billing in Q1 FY2025-26, and what was their top product category during that quarter?",
  "plan": {
   "parts": [
    {
     "id": 1,
     "ask": "rank",
     "metrics": [
      "sales"
     ],
     "filters": [
      {
       "column": "PartyType",
       "op": "==",
       "value": "B2B Dealer"
      },
      {
       "column": "PartyState",
       "op": "==",
       "value": "Gujarat"
      }
     ],
     "period": {
      "start": "2025-04-01",
      "end": "2025-06-30",
      "label": "Q1 FY2025-26"
     },
     "group_by": "PartyName",
     "order": "desc",
     "limit": 1
    },
    {
     "id": 2,
     "ask": "rank",
     "metrics": [
      "sales"
     ],
     "filters": [
      {
       "column": "PartyType",
       "op": "==",
       "value": "B2B Dealer"
      },
      {
       "column": "PartyState",
       "op": "==",
       "value": "Gujarat"
      }
     ],
     "period": {
      "start": "2025-04-01",
      "end": "2025-06-30",
      "label": "Q1 FY2025-26"
     },
     "group_by": "Category",
     "order": "desc",
     "limit": 1,
     "depends_on": {
      "part": 1,
      "column": "PartyName"
     }
    }
   ]
  }
 },
 {
  "question": "Within the 'Jewellery (Artificial)' category across the entire dataset, which top 2 products generated the highest total net profit",
  "plan": {
   "parts": [
    {
     "id": 1,
     "ask": "rank",
     "metrics": [
      "profit"
     ],
     "filters": [
      {
       "column": "Category",
       "op": "==",
       "value": "Jewellery (Artificial)"
      }
     ],
     "group_by": "Product",
     "order": "desc",
     "limit": 2
    }
   ]
  }
 },
 {
  "question": "Which state generated the highest gross sales revenue for the 'Smart Watch' in FY2025-26",
  "plan": {
   "parts": [
    {
     "id": 1,
     "ask": "rank",
     "metrics": [
      "sales"
     ],
     "filters": [
      {
       "column": "Product",
       "op": "==",
       "value": "Smart Watch"
      }
     ],
     "period": {
      "start": "2025-04-01",
      "end": "2026-03-31",
      "label": "FY2025-26"
     },
     "group_by": "PartyState",
     "order": "desc",
     "limit": 1
    }
   ]
  }
 },
 {
  "question": "In which calendar month was the highest total CGST collected during FY2025-26",
  "plan": {
   "parts": [
    {
     "id": 1,
     "ask": "rank",
     "metrics": [
      "cgst"
     ],
     "period": {
      "start": "2025-04-01",
      "end": "2026-03-31",
      "label": "FY2025-26"
     },
     "group_by": "Month",
     "order": "desc",
     "limit": 1
    }
   ]
  }
 },
 {
  "question": "What was the total sales revenue generated via 'Bank Transfer' from customers in Karnataka during FY2025-26?",
  "plan": {
   "parts": [
    {
     "id": 1,
     "ask": "total",
     "metrics": [
      "sales"
     ],
     "filters": [
      {
       "column": "PaymentMode",
       "op": "==",
       "value": "Bank Transfer"
      },
      {
       "column": "PartyState",
       "op": "==",
       "value": "Karnataka"
      }
     ],
     "period": {
      "start": "2025-04-01",
      "end": "2026-03-31",
      "label": "FY2025-26"
     }
    }
   ]
  }
 },
 {
  "question": "Which product in the 'Mobile Accessories' category generated the highest net profit in FY2025-26?",
  "plan": {
   "parts": [
    {
     "id": 1,
     "ask": "rank",
     "metrics": [
      "profit"
     ],
     "filters": [
      {
       "column": "Category",
       "op": "==",
       "value": "Mobile Accessories"
      }
     ],
     "period": {
      "start": "2025-04-01",
      "end": "2026-03-31",
      "label": "FY2025-26"
     },
     "group_by": "Product",
     "order": "desc",
     "limit": 1
    }
   ]
  }
 },
 {
  "question": "Who were the top 2 B2B Dealers by total IGST paid across the entire dataset?",
  "plan": {
   "parts": [
    {
     "id": 1,
     "ask": "rank",
     "metrics": [
      "igst"
     ],
     "filters": [
      {
       "column": "PartyType",
       "op": "==",
       "value": "B2B Dealer"
      }
     ],
     "group_by": "PartyName",
     "order": "desc",
     "limit": 2
    }
   ]
  }
 },
 {
  "question": "What is the total IGST collected from Retail Customers located in Uttar Pradesh across the entire dataset?",
  "plan": {
   "parts": [
    {
     "id": 1,
     "ask": "total",
     "metrics": [
      "igst"
     ],
     "filters": [
      {
       "column": "PartyType",
       "op": "==",
       "value": "Retail Customer"
      },
      {
       "column": "PartyState",
       "op": "==",
       "value": "Uttar Pradesh"
      }
     ]
    }
   ]
  }
 },
 {
  "question": "Which specific product in the Bags category had the highest unit quantity sold in Q3 FY2025-26 (Oct–Dec 2025)",
  "plan": {
   "parts": [
    {
     "id": 1,
     "ask": "rank",
     "metrics": [
      "quantity"
     ],
     "filters": [
      {
       "column": "Category",
       "op": "==",
       "value": "Bags"
      }
     ],
     "period": {
      "start": "2025-10-01",
      "end": "2025-12-31",
      "label": "Q3 FY2025-26"
     },
     "group_by": "Product",
     "order": "desc",
     "limit": 1
    }
   ]
  }
 },
 {
  "question": "Which product category had the lowest profit margin percentage (Profit/Taxable Amount) in Q4 FY2025-26 (Jan–Mar 2026)",
  "plan": {
   "parts": [
    {
     "id": 1,
     "ask": "rank",
     "metrics": [
      "margin"
     ],
     "period": {
      "start": "2026-01-01",
      "end": "2026-03-31",
      "label": "Q4 FY2025-26"
     },
     "group_by": "Category",
     "order": "asc",
     "limit": 1
    }
   ]
  }
 },
 {
  "question": "What was the exact profit margin percentage of the 'Silk Scarf' in Q3 FY2025-26 (Oct–Dec 2025)",
  "plan": {
   "parts": [
    {
     "id": 1,
     "ask": "total",
     "metrics": [
      "margin"
     ],
     "filters": [
      {
       "column": "Product",
       "op": "==",
       "value": "Silk Scarf"
      }
     ],
     "period": {
      "start": "2025-10-01",
      "end": "2025-12-31",
      "label": "Q3 FY2025-26"
     }
    }
   ]
  }
 },
 {
  "question": "compare the sales revenue of the 'Caps & Hats' category between Q1 FY2025-26 (Apr–Jun 2025) and Q1 FY2026-27 (Apr–Jun 2026)",
  "plan": {
   "parts": [
    {
     "id": 1,
     "ask": "compare",
     "metrics": [
      "sales"
     ],
     "filters": [
      {
       "column": "Category",
       "op": "==",
       "value": "Caps & Hats"
      }
     ],
     "periods": [
      {
       "start": "2025-04-01",
       "end": "2025-06-30",
       "label": "Q1 FY2025-26"
      },
      {
       "start": "2026-04-01",
       "end": "2026-06-30",
       "label": "Q1 FY2026-27"
      }
     ]
    }
   ]
  }
 },
 {
  "question": "What was the average ticket size (gross sales revenue per unique invoice) for Cash transactions in Q4 FY2025-26 (Jan–Mar 2026)",
  "plan": {
   "parts": [
    {
     "id": 1,
     "ask": "total",
     "metrics": [
      "ticket"
     ],
     "filters": [
      {
       "column": "PaymentMode",
       "op": "==",
       "value": "Cash"
      }
     ],
     "period": {
      "start": "2026-01-01",
      "end": "2026-03-31",
      "label": "Q4 FY2025-26"
     }
    }
   ]
  }
 },
 {
  "question": "Who was the top customer by gross billing in Rajasthan across the entire dataset within FY2025-26.",
  "plan": {
   "parts": [
    {
     "id": 1,
     "ask": "rank",
     "metrics": [
      "sales"
     ],
     "filters": [
      {
       "column": "PartyState",
       "op": "==",
       "value": "Rajasthan"
      }
     ],
     "group_by": "PartyName",
     "order": "desc",
     "limit": 1
    }
   ],
   "assumptions": [
    "'entire dataset' overrides the FY mention"
   ]
  }
 },
 {
  "question": "Who was the top Online Marketplace Buyer by total gross billing in FY2025-26, and how much did they spend",
  "plan": {
   "parts": [
    {
     "id": 1,
     "ask": "rank",
     "metrics": [
      "sales"
     ],
     "filters": [
      {
       "column": "PartyType",
       "op": "==",
       "value": "Online Marketplace Buyer"
      }
     ],
     "period": {
      "start": "2025-04-01",
      "end": "2026-03-31",
      "label": "FY2025-26"
     },
     "group_by": "PartyName",
     "order": "desc",
     "limit": 1
    }
   ]
  }
 }
]