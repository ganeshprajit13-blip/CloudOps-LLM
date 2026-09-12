#!/usr/bin/env python3
"""
Demo: Deep Research RCA Agent

This demonstrates the Deep Research pattern for incident investigation using LangGraph:

1. ENRICHMENT: Gather context from knowledge base, runbooks, past incidents
2. HYPOTHESIS GENERATION: Use enriched context to generate hypotheses
3. DYNAMIC AGENT SPAWNING: Create investigation agents on-the-fly (one per hypothesis)
4. SYNTHESIS: Compare evidence across all investigations

Run: python run_demo.py [scenario_name]
"""

from rca_agent import main

if __name__ == "__main__":
    main()
