"""
Knowledge Database Tool

Provides intelligent storage and retrieval of questions/solutions with keyword-based search.
AI can use this tool to:
1. Search for similar problems and solutions
2. Add new knowledge when problems are solved
3. Update existing knowledge entries
"""

import logging
import re
import json
import time
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field

from one_think.tools.base import Tool, ToolResponse
from one_think.tools.knowledge_storage import get_storage

logger = logging.getLogger(__name__)


class KnowledgeDatabaseTool(Tool):
    """Knowledge database tool for storing and searching Q&A knowledge."""
    
    name = "knowledge_database"
    description = "Intelligent knowledge database for storing and searching questions/solutions"
    version = "1.0.0"
    
    # Pydantic schemas for validation
    class Input(BaseModel):
        """Input parameters for knowledge database operations."""
        operation: Literal["search_by_keywords", "add_knowledge", "update_knowledge", "get_popular", "get_stats"] = Field(
            description="Operation to perform"
        )
        keywords: Optional[str] = Field(
            default=None, 
            description="Keywords for search (comma-separated or space-separated)"
        )
        question: Optional[str] = Field(
            default=None,
            description="Question or problem description (for add/update operations)"
        )
        solution: Optional[str] = Field(
            default=None,
            description="Solution or resolution description (for add/update operations)"
        )
        entry_id: Optional[int] = Field(
            default=None,
            description="ID of knowledge entry to update"
        )
        limit: Optional[int] = Field(
            default=5,
            ge=1,
            le=50,
            description="Maximum number of results to return"
        )
    
    class Output(BaseModel):
        """Output structure for knowledge database operations."""
        found_entries: Optional[int] = Field(default=None, description="Number of entries found")
        search_keywords: Optional[List[str]] = Field(default=None, description="Extracted search keywords")
        results: Optional[List[Dict[str, Any]]] = Field(default=None, description="Search results")
        entry_id: Optional[int] = Field(default=None, description="ID of created/updated entry")
        message: Optional[str] = Field(default=None, description="Status message")
        extracted_keywords: Optional[Dict[str, List[str]]] = Field(default=None, description="AI-extracted keywords")
        popular_entries: Optional[List[Dict[str, Any]]] = Field(default=None, description="Popular entries list")
        count: Optional[int] = Field(default=None, description="Count of entries")
        entry_count: Optional[int] = Field(default=None, description="Total entries in database")
        database_size_bytes: Optional[int] = Field(default=None, description="Database file size")
        database_path: Optional[str] = Field(default=None, description="Database file path")
        most_accessed_question: Optional[str] = Field(default=None, description="Most accessed question")
        max_access_count: Optional[int] = Field(default=None, description="Highest access count")
        error: Optional[str] = Field(default=None, description="Error message if operation failed")
    
    def __init__(self):
        super().__init__()
        self.storage = get_storage()
    
    def execute_json(self, params: Dict[str, Any], request_id: Optional[str] = None) -> ToolResponse:
        """Execute knowledge database operation with JSON validation."""
        start_time = time.time()
        
        try:
            # Validate input parameters
            validated_input = self.validate_input(params)
            
            # Execute operation
            if validated_input.operation == "search_by_keywords":
                result = self._search_by_keywords(validated_input)
            elif validated_input.operation == "add_knowledge":
                result = self._add_knowledge(validated_input)
            elif validated_input.operation == "update_knowledge":
                result = self._update_knowledge(validated_input)
            elif validated_input.operation == "get_popular":
                result = self._get_popular(validated_input)
            elif validated_input.operation == "get_stats":
                result = self._get_stats()
            else:
                return ToolResponse(
                    status="error",
                    tool=self.name,
                    request_id=request_id,
                    error={"type": "invalid_operation", "message": f"Unknown operation: {validated_input.operation}"},
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            
            # Validate output
            if result.get("success", True):
                validated_output = self.validate_output(result)
                return ToolResponse(
                    status="success",
                    tool=self.name,
                    request_id=request_id,
                    result=validated_output.model_dump(exclude_none=True),
                    execution_time_ms=(time.time() - start_time) * 1000
                )
            else:
                return ToolResponse(
                    status="error",
                    tool=self.name,
                    request_id=request_id,
                    error={"type": "operation_error", "message": result.get("error", "Operation failed")},
                    execution_time_ms=(time.time() - start_time) * 1000
                )
                
        except Exception as e:
            logger.error(f"Knowledge database error: {e}")
            return ToolResponse(
                status="error",
                tool=self.name,
                request_id=request_id,
                error={"type": "execution_error", "message": str(e)},
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def get_help(self) -> str:
        """Return detailed help for the knowledge database tool."""
        return """
KNOWLEDGE DATABASE TOOL

A persistent knowledge base for storing and searching question/solution pairs.
Use this tool to leverage previous problem-solving experiences.

OPERATIONS:

1. search_by_keywords - Search existing knowledge
   Parameters:
   - keywords (required): Space or comma-separated keywords
   - limit (optional): Max results (1-50, default: 5)
   
   Example: {"operation": "search_by_keywords", "keywords": "messenger kontakt szukanie", "limit": 3}

2. add_knowledge - Store new question/solution
   Parameters:
   - question (required): Problem description
   - solution (required): Solution description
   
   Example: {"operation": "add_knowledge", "question": "API timeout error", "solution": "increased timeout and added retry logic"}

3. update_knowledge - Update existing entry
   Parameters:
   - entry_id (required): ID of entry to update
   - question (required): Updated problem description
   - solution (required): Updated solution description
   
   Example: {"operation": "update_knowledge", "entry_id": 5, "question": "...", "solution": "..."}

4. get_popular - Get most accessed solutions
   Parameters:
   - limit (optional): Max results (default: 10)
   
   Example: {"operation": "get_popular", "limit": 5}

5. get_stats - Database statistics
   Parameters: None
   
   Example: {"operation": "get_stats"}

WHEN TO USE:
- When uncertain about answering user questions
- Before solving problems (check if solution exists)
- After solving new problems (store for future reference)
- To find frequently accessed solutions

SEARCH TIPS:
- Use relevant keywords from the user's question
- Try both Polish and English keywords
- Include domain-specific terms (messenger, api, timeout, etc.)

The tool automatically extracts and normalizes keywords for optimal search results.
        """.strip()
    
    def _search_by_keywords(self, validated_input) -> Dict[str, Any]:
        """Search knowledge database by keywords."""
        if not validated_input.keywords:
            return {"success": False, "error": "Keywords parameter is required for search"}
        
        # Extract and normalize keywords
        keywords = self._extract_keywords(validated_input.keywords)
        
        try:
            # Multi-stage search for best results
            results = []
            limit = validated_input.limit
            
            # Stage 1: Exact keyword match in question keywords
            question_results = self._search_question_keywords(keywords, limit)
            results.extend(question_results)
            
            # Stage 2: Exact keyword match in solution keywords  
            if len(results) < limit:
                solution_results = self._search_solution_keywords(keywords, limit - len(results))
                results.extend(solution_results)
            
            # Stage 3: Full-text search if needed
            if len(results) < limit:
                fts_results = self._search_full_text(validated_input.keywords, limit - len(results))
                results.extend(fts_results)
            
            # Remove duplicates and rank
            unique_results = self._deduplicate_and_rank(results, keywords)
            
            # Update access counts
            for result in unique_results[:3]:  # Only top 3 to avoid spam
                self._increment_access_count(result['id'])
            
            return {
                "found_entries": len(unique_results),
                "search_keywords": keywords,
                "results": unique_results[:limit]
            }
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return {"success": False, "error": f"Search failed: {str(e)}"}
    
    def _add_knowledge(self, validated_input) -> Dict[str, Any]:
        """Add new knowledge entry."""
        if not validated_input.question or not validated_input.solution:
            return {"success": False, "error": "Both question and solution are required"}
        
        try:
            # Extract keywords
            question_keywords = self._extract_keywords(validated_input.question)
            solution_keywords = self._extract_keywords(validated_input.solution)
            all_keywords = list(set(question_keywords + solution_keywords))
            
            # Insert into database
            insert_id = self.storage.execute_insert("""
                INSERT INTO knowledge_entries 
                (question, solution, question_keywords, solution_keywords, all_keywords)
                VALUES (?, ?, ?, ?, ?)
            """, (
                validated_input.question,
                validated_input.solution, 
                ",".join(question_keywords),
                ",".join(solution_keywords),
                ",".join(all_keywords)
            ))
            
            logger.info(f"Added new knowledge entry with ID: {insert_id}")
            
            return {
                "entry_id": insert_id,
                "message": "Knowledge entry added successfully",
                "extracted_keywords": {
                    "question_keywords": question_keywords,
                    "solution_keywords": solution_keywords
                }
            }
            
        except Exception as e:
            logger.error(f"Add knowledge error: {e}")
            return {"success": False, "error": f"Failed to add knowledge: {str(e)}"}
    
    def _update_knowledge(self, validated_input) -> Dict[str, Any]:
        """Update existing knowledge entry."""
        if not validated_input.entry_id:
            return {"success": False, "error": "entry_id is required for update operation"}
        
        if not validated_input.question or not validated_input.solution:
            return {"success": False, "error": "Both question and solution are required for update"}
        
        try:
            # Check if entry exists
            existing = self.storage.execute_query(
                "SELECT id FROM knowledge_entries WHERE id = ?",
                (validated_input.entry_id,)
            )
            
            if not existing:
                return {"success": False, "error": f"Knowledge entry with ID {validated_input.entry_id} not found"}
            
            # Extract keywords
            question_keywords = self._extract_keywords(validated_input.question)
            solution_keywords = self._extract_keywords(validated_input.solution)
            all_keywords = list(set(question_keywords + solution_keywords))
            
            # Update database
            rows_updated = self.storage.execute_update("""
                UPDATE knowledge_entries
                SET question = ?, solution = ?, 
                    question_keywords = ?, solution_keywords = ?, all_keywords = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                validated_input.question,
                validated_input.solution,
                ",".join(question_keywords), 
                ",".join(solution_keywords),
                ",".join(all_keywords),
                validated_input.entry_id
            ))
            
            if rows_updated > 0:
                logger.info(f"Updated knowledge entry ID: {validated_input.entry_id}")
                return {
                    "entry_id": validated_input.entry_id,
                    "message": "Knowledge entry updated successfully",
                    "extracted_keywords": {
                        "question_keywords": question_keywords,
                        "solution_keywords": solution_keywords
                    }
                }
            else:
                return {"success": False, "error": "No rows were updated"}
                
        except Exception as e:
            logger.error(f"Update knowledge error: {e}")
            return {"success": False, "error": f"Failed to update knowledge: {str(e)}"}
    
    def _get_popular(self, validated_input) -> Dict[str, Any]:
        """Get most popular/accessed knowledge entries."""
        limit = validated_input.limit or 10
        
        try:
            results = self.storage.execute_query("""
                SELECT id, question, solution, access_count, last_accessed
                FROM knowledge_entries 
                WHERE access_count > 0
                ORDER BY access_count DESC, updated_at DESC
                LIMIT ?
            """, (limit,))
            
            return {
                "popular_entries": results,
                "count": len(results)
            }
            
        except Exception as e:
            logger.error(f"Get popular error: {e}")
            return {"success": False, "error": f"Failed to get popular entries: {str(e)}"}
    
    def _get_stats(self) -> Dict[str, Any]:
        """Get knowledge database statistics."""
        try:
            stats = self.storage.get_stats()
            return stats
            
        except Exception as e:
            logger.error(f"Get stats error: {e}")
            return {"success": False, "error": f"Failed to get stats: {str(e)}"}
    
    # Pozostałe helper methods bez zmian...
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text using simple NLP techniques."""
        if not text:
            return []
        
        # Normalize text
        text = text.lower()
        
        # Remove special characters but keep Polish characters
        text = re.sub(r'[^\w\sąćęłńóśźż]', ' ', text)
        
        # Split into words
        words = text.split()
        
        # Filter out common stop words (Polish + English)
        stop_words = {
            'i', 'a', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'że', 'się', 'nie', 'na', 'do', 'w', 'z', 'o', 'po', 'za', 'od', 'przed', 'nad', 'pod',
            'czy', 'jak', 'co', 'gdzie', 'kiedy', 'dlaczego', 'który', 'która', 'które', 'jest', 'są',
            'was', 'were', 'is', 'are', 'this', 'that', 'these', 'those', 'can', 'could', 'should'
        }
        
        # Filter meaningful words (length >= 3, not in stop words)
        keywords = [
            word for word in words 
            if len(word) >= 3 and word not in stop_words
        ]
        
        # Remove duplicates while preserving order
        unique_keywords = []
        seen = set()
        for keyword in keywords:
            if keyword not in seen:
                unique_keywords.append(keyword)
                seen.add(keyword)
        
        return unique_keywords[:10]  # Limit to top 10 keywords
    
    def _search_question_keywords(self, keywords: List[str], limit: int) -> List[Dict[str, Any]]:
        """Search in question keywords with exact matching."""
        if not keywords:
            return []
        
        # Create LIKE patterns for each keyword
        like_patterns = [f"%{keyword}%" for keyword in keywords]
        where_clauses = ["question_keywords LIKE ?" for _ in keywords]
        where_sql = " AND ".join(where_clauses)
        
        results = self.storage.execute_query(f"""
            SELECT id, question, solution, question_keywords, solution_keywords, access_count
            FROM knowledge_entries
            WHERE {where_sql}
            ORDER BY access_count DESC, created_at DESC
            LIMIT ?
        """, tuple(like_patterns + [limit]))
        
        # Add match score
        for result in results:
            result['match_type'] = 'question_keywords'
            result['match_score'] = self._calculate_match_score(result['question_keywords'], keywords)
        
        return results
    
    def _search_solution_keywords(self, keywords: List[str], limit: int) -> List[Dict[str, Any]]:
        """Search in solution keywords with exact matching."""
        if not keywords:
            return []
        
        like_patterns = [f"%{keyword}%" for keyword in keywords]
        where_clauses = ["solution_keywords LIKE ?" for _ in keywords]
        where_sql = " OR ".join(where_clauses)
        
        results = self.storage.execute_query(f"""
            SELECT id, question, solution, question_keywords, solution_keywords, access_count
            FROM knowledge_entries
            WHERE {where_sql}
            ORDER BY access_count DESC, created_at DESC
            LIMIT ?
        """, tuple(like_patterns + [limit]))
        
        for result in results:
            result['match_type'] = 'solution_keywords'
            result['match_score'] = self._calculate_match_score(result['solution_keywords'], keywords)
        
        return results
    
    def _search_full_text(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Full-text search using FTS5."""
        if not query.strip():
            return []
        
        try:
            results = self.storage.execute_query("""
                SELECT ke.id, ke.question, ke.solution, ke.question_keywords, 
                       ke.solution_keywords, ke.access_count
                FROM knowledge_fts
                JOIN knowledge_entries ke ON knowledge_fts.rowid = ke.id
                WHERE knowledge_fts MATCH ?
                ORDER BY rank, ke.access_count DESC
                LIMIT ?
            """, (query, limit))
            
            for result in results:
                result['match_type'] = 'full_text'
                result['match_score'] = 0.5  # Lower score for FTS matches
            
            return results
            
        except Exception as e:
            logger.warning(f"FTS search failed: {e}")
            return []
    
    def _calculate_match_score(self, entry_keywords: str, search_keywords: List[str]) -> float:
        """Calculate match score between entry keywords and search keywords."""
        if not entry_keywords or not search_keywords:
            return 0.0
        
        entry_kw_list = entry_keywords.lower().split(',')
        search_kw_lower = [kw.lower() for kw in search_keywords]
        
        matches = 0
        for search_kw in search_kw_lower:
            if any(search_kw in entry_kw for entry_kw in entry_kw_list):
                matches += 1
        
        return matches / len(search_keywords)
    
    def _deduplicate_and_rank(self, results: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
        """Remove duplicates and rank results by relevance."""
        seen_ids = set()
        unique_results = []
        
        for result in results:
            if result['id'] not in seen_ids:
                seen_ids.add(result['id'])
                unique_results.append(result)
        
        # Sort by match score desc, then access count desc
        unique_results.sort(
            key=lambda x: (x['match_score'], x['access_count']), 
            reverse=True
        )
        
        return unique_results
    
    def _increment_access_count(self, entry_id: int):
        """Increment access count for a knowledge entry."""
        try:
            self.storage.execute_update("""
                UPDATE knowledge_entries 
                SET access_count = access_count + 1, 
                    last_accessed = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (entry_id,))
        except Exception as e:
            logger.warning(f"Failed to increment access count for entry {entry_id}: {e}")


# Register tool
def register():
    return KnowledgeDatabaseTool()
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text using simple NLP techniques."""
        if not text:
            return []
        
        # Normalize text
        text = text.lower()
        
        # Remove special characters but keep Polish characters
        text = re.sub(r'[^\w\sąćęłńóśźż]', ' ', text)
        
        # Split into words
        words = text.split()
        
        # Filter out common stop words (Polish + English)
        stop_words = {
            'i', 'a', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'że', 'się', 'nie', 'na', 'do', 'w', 'z', 'o', 'po', 'za', 'od', 'przed', 'nad', 'pod',
            'czy', 'jak', 'co', 'gdzie', 'kiedy', 'dlaczego', 'który', 'która', 'które', 'jest', 'są',
            'was', 'were', 'is', 'are', 'this', 'that', 'these', 'those', 'can', 'could', 'should'
        }
        
        # Filter meaningful words (length >= 3, not in stop words)
        keywords = [
            word for word in words 
            if len(word) >= 3 and word not in stop_words
        ]
        
        # Remove duplicates while preserving order
        unique_keywords = []
        seen = set()
        for keyword in keywords:
            if keyword not in seen:
                unique_keywords.append(keyword)
                seen.add(keyword)
        
        return unique_keywords[:10]  # Limit to top 10 keywords
    
    def _search_question_keywords(self, keywords: List[str], limit: int) -> List[Dict[str, Any]]:
        """Search in question keywords with exact matching."""
        if not keywords:
            return []
        
        # Create LIKE patterns for each keyword
        like_patterns = [f"%{keyword}%" for keyword in keywords]
        where_clauses = ["question_keywords LIKE ?" for _ in keywords]
        where_sql = " AND ".join(where_clauses)
        
        results = self.storage.execute_query(f"""
            SELECT id, question, solution, question_keywords, solution_keywords, access_count
            FROM knowledge_entries
            WHERE {where_sql}
            ORDER BY access_count DESC, created_at DESC
            LIMIT ?
        """, tuple(like_patterns + [limit]))
        
        # Add match score
        for result in results:
            result['match_type'] = 'question_keywords'
            result['match_score'] = self._calculate_match_score(result['question_keywords'], keywords)
        
        return results
    
    def _search_solution_keywords(self, keywords: List[str], limit: int) -> List[Dict[str, Any]]:
        """Search in solution keywords with exact matching."""
        if not keywords:
            return []
        
        like_patterns = [f"%{keyword}%" for keyword in keywords]
        where_clauses = ["solution_keywords LIKE ?" for _ in keywords]
        where_sql = " OR ".join(where_clauses)
        
        results = self.storage.execute_query(f"""
            SELECT id, question, solution, question_keywords, solution_keywords, access_count
            FROM knowledge_entries
            WHERE {where_sql}
            ORDER BY access_count DESC, created_at DESC
            LIMIT ?
        """, tuple(like_patterns + [limit]))
        
        for result in results:
            result['match_type'] = 'solution_keywords'
            result['match_score'] = self._calculate_match_score(result['solution_keywords'], keywords)
        
        return results
    
    def _search_full_text(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Full-text search using FTS5."""
        if not query.strip():
            return []
        
        try:
            results = self.storage.execute_query("""
                SELECT ke.id, ke.question, ke.solution, ke.question_keywords, 
                       ke.solution_keywords, ke.access_count
                FROM knowledge_fts
                JOIN knowledge_entries ke ON knowledge_fts.rowid = ke.id
                WHERE knowledge_fts MATCH ?
                ORDER BY rank, ke.access_count DESC
                LIMIT ?
            """, (query, limit))
            
            for result in results:
                result['match_type'] = 'full_text'
                result['match_score'] = 0.5  # Lower score for FTS matches
            
            return results
            
        except Exception as e:
            logger.warning(f"FTS search failed: {e}")
            return []
    
    def _calculate_match_score(self, entry_keywords: str, search_keywords: List[str]) -> float:
        """Calculate match score between entry keywords and search keywords."""
        if not entry_keywords or not search_keywords:
            return 0.0
        
        entry_kw_list = entry_keywords.lower().split(',')
        search_kw_lower = [kw.lower() for kw in search_keywords]
        
        matches = 0
        for search_kw in search_kw_lower:
            if any(search_kw in entry_kw for entry_kw in entry_kw_list):
                matches += 1
        
        return matches / len(search_keywords)
    
    def _deduplicate_and_rank(self, results: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
        """Remove duplicates and rank results by relevance."""
        seen_ids = set()
        unique_results = []
        
        for result in results:
            if result['id'] not in seen_ids:
                seen_ids.add(result['id'])
                unique_results.append(result)
        
        # Sort by match score desc, then access count desc
        unique_results.sort(
            key=lambda x: (x['match_score'], x['access_count']), 
            reverse=True
        )
        
        return unique_results
    
    def _increment_access_count(self, entry_id: int):
        """Increment access count for a knowledge entry."""
        try:
            self.storage.execute_update("""
                UPDATE knowledge_entries 
                SET access_count = access_count + 1, 
                    last_accessed = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (entry_id,))
        except Exception as e:
            logger.warning(f"Failed to increment access count for entry {entry_id}: {e}")


# Register tool
def register():
    return KnowledgeDatabaseTool()