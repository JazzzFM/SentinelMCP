from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
import json

# Import our services
from rag.retriever import RetrievalService
from app.mcp_server import create_mcp_server

logger = logging.getLogger(__name__)

class Agent:
    """Base agent class"""
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process agent-specific logic"""
        raise NotImplementedError

class PlanningAgent(Agent):
    """Agent responsible for planning and query reformulation"""
    def __init__(self):
        super().__init__("PlanningAgent", "Plans and reformulates user queries")
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        question = context.get('question', '')
        
        # Simple query analysis and reformulation
        plan = {
            'original_question': question,
            'reformulated_query': self._reformulate_query(question),
            'retrieval_strategy': 'semantic_search',
            'requires_tools': self._analyze_tool_requirements(question),
            'estimated_complexity': 'medium'
        }
        
        logger.info(f"Planning completed for question: {question[:50]}...")
        return {'plan': plan, 'next_agent': 'retrieval'}
    
    def _reformulate_query(self, question: str) -> str:
        """Simple query reformulation logic"""
        # Remove question words and focus on key terms
        reformulated = question.lower()
        question_words = ['what', 'how', 'why', 'when', 'where', 'who', 'which']
        for word in question_words:
            reformulated = reformulated.replace(f"{word} ", "")
        return reformulated.strip()
    
    def _analyze_tool_requirements(self, question: str) -> List[str]:
        """Analyze if question requires specific tools"""
        tools_needed = []
        question_lower = question.lower()
        
        if any(term in question_lower for term in ['cfdi', 'factura', 'invoice']):
            tools_needed.append('consultar_cfdi')
        if any(term in question_lower for term in ['curp', 'identidad', 'identity']):
            tools_needed.append('consultar_curp')
        if any(term in question_lower for term in ['wikipedia', 'wiki']):
            tools_needed.append('wikipedia_search')
        if any(term in question_lower for term in ['document', 'pdf', 'texto']):
            tools_needed.append('obtener_texto_en_documento')
            
        return tools_needed

class RetrievalAgent(Agent):
    """Agent responsible for retrieving relevant documents"""
    def __init__(self, retrieval_service: RetrievalService):
        super().__init__("RetrievalAgent", "Retrieves relevant documents using semantic search")
        self.retrieval_service = retrieval_service
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        plan = context.get('plan', {})
        k = context.get('k', 5)
        
        query = plan.get('reformulated_query', context.get('question', ''))
        
        # Perform retrieval
        documents = self.retrieval_service.retrieve(query, k)
        
        retrieval_result = {
            'query_used': query,
            'documents_found': len(documents),
            'documents': documents
        }
        
        logger.info(f"Retrieved {len(documents)} documents for query: {query[:50]}...")
        return {'retrieval_result': retrieval_result, 'next_agent': 'analysis'}

class AnalysisAgent(Agent):
    """Agent responsible for analyzing retrieved documents and generating responses"""
    def __init__(self, mcp_server):
        super().__init__("AnalysisAgent", "Analyzes documents and generates responses")
        self.mcp_server = mcp_server
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        question = context.get('question', '')
        plan = context.get('plan', {})
        retrieval_result = context.get('retrieval_result', {})
        
        documents = retrieval_result.get('documents', [])
        
        # Generate response based on retrieved documents
        response = self._generate_response(question, documents, plan)
        
        # Execute tools if needed
        tool_results = {}
        required_tools = plan.get('requires_tools', [])
        if required_tools:
            tool_results = self._execute_tools(required_tools, context)
        
        analysis_result = {
            'response': response,
            'tool_results': tool_results,
            'sources': [doc.get('source', 'unknown') for doc in documents],
            'confidence': self._calculate_confidence(documents)
        }
        
        logger.info(f"Analysis completed for question: {question[:50]}...")
        return {'analysis_result': analysis_result, 'next_agent': 'guard'}
    
    def _generate_response(self, question: str, documents: List[Dict], plan: Dict) -> str:
        """Generate response based on retrieved documents"""
        if not documents:
            return f"I couldn't find relevant information to answer: {question}"
        
        # Simple response generation
        context_snippets = []
        for doc in documents[:3]:  # Use top 3 documents
            content = doc.get('content', '')[:200]  # First 200 chars
            source = doc.get('source', 'unknown')
            context_snippets.append(f"From {source}: {content}")
        
        response = f"Based on the available documents, here's what I found regarding '{question}':\n\n"
        response += "\n\n".join(context_snippets)
        response += "\n\nThis information is based on the retrieved documents. For more specific details, please refer to the source documents."
        
        return response
    
    def _execute_tools(self, required_tools: List[str], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute required MCP tools"""
        tool_results = {}
        
        for tool_name in required_tools:
            if tool_name in self.mcp_server.tools:
                try:
                    # This is simplified - in practice, you'd extract parameters from context
                    if tool_name == 'wikipedia_search':
                        question = context.get('question', '')
                        result = self.mcp_server.tools[tool_name](query=question)
                        tool_results[tool_name] = result
                    else:
                        tool_results[tool_name] = f"Tool {tool_name} requires specific parameters"
                except Exception as e:
                    tool_results[tool_name] = f"Error executing {tool_name}: {str(e)}"
        
        return tool_results
    
    def _calculate_confidence(self, documents: List[Dict]) -> float:
        """Calculate confidence score based on retrieved documents"""
        if not documents:
            return 0.0
        
        # Simple confidence calculation based on number of documents and their distances
        base_confidence = min(len(documents) * 0.2, 1.0)  # More docs = higher confidence
        
        # Adjust based on distance/similarity scores if available
        distances = [doc.get('distance', 0.5) for doc in documents]
        avg_distance = sum(distances) / len(distances) if distances else 0.5
        distance_factor = max(0.1, 1.0 - avg_distance)  # Lower distance = higher confidence
        
        return min(base_confidence * distance_factor, 1.0)

class GuardAgent(Agent):
    """Agent responsible for policy checking and compliance"""
    def __init__(self):
        super().__init__("GuardAgent", "Validates responses against policies and compliance rules")
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        analysis_result = context.get('analysis_result', {})
        response = analysis_result.get('response', '')
        
        # Simple policy checks
        policy_check = self._check_policies(response, context)
        
        guard_result = {
            'policy_approved': policy_check['approved'],
            'policy_violations': policy_check['violations'],
            'requires_human_review': policy_check['requires_review'],
            'modified_response': policy_check.get('modified_response', response)
        }
        
        next_agent = 'human' if policy_check['requires_review'] else 'complete'
        
        logger.info(f"Guard check completed - Approved: {policy_check['approved']}")
        return {'guard_result': guard_result, 'next_agent': next_agent}
    
    def _check_policies(self, response: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Simple policy checking logic"""
        violations = []
        requires_review = False
        
        # Check for sensitive information
        sensitive_patterns = ['password', 'ssn', 'credit card', 'api key']
        response_lower = response.lower()
        
        for pattern in sensitive_patterns:
            if pattern in response_lower:
                violations.append(f"Contains potentially sensitive information: {pattern}")
                requires_review = True
        
        # Check response length (very long responses might need review)
        if len(response) > 2000:
            violations.append("Response is very long and may need human review")
            requires_review = True
        
        approved = len(violations) == 0
        
        return {
            'approved': approved,
            'violations': violations,
            'requires_review': requires_review
        }

class AgentOrchestrator:
    """Main orchestrator that manages the multi-agent workflow"""
    
    def __init__(self, vector_store_path: str = "./chroma_db"):
        # Initialize services
        self.retrieval_service = RetrievalService(vector_store_path)
        self.mcp_server = create_mcp_server()
        
        # Initialize agents
        self.agents = {
            'planning': PlanningAgent(),
            'retrieval': RetrievalAgent(self.retrieval_service),
            'analysis': AnalysisAgent(self.mcp_server),
            'guard': GuardAgent()
        }
        
        # Workflow state
        self.conversation_history = []
        
    def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main processing method that orchestrates the agent workflow
        """
        start_time = datetime.now()
        conversation_id = f"conv_{int(start_time.timestamp())}"
        
        # Initialize context
        context = {
            'conversation_id': conversation_id,
            'timestamp': start_time.isoformat(),
            **request
        }
        
        # Execute agent workflow
        workflow_result = self._execute_workflow(context)
        
        # Prepare final response
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        final_response = {
            'conversation_id': conversation_id,
            'question': request.get('question', ''),
            'response': workflow_result.get('final_response', 'No response generated'),
            'sources': workflow_result.get('sources', []),
            'tool_results': workflow_result.get('tool_results', {}),
            'confidence': workflow_result.get('confidence', 0.0),
            'processing_time_seconds': processing_time,
            'requires_human_review': workflow_result.get('requires_human_review', False),
            'workflow_trace': workflow_result.get('trace', [])
        }
        
        # Store in conversation history
        self.conversation_history.append(final_response)
        
        logger.info(f"Request processed in {processing_time:.2f} seconds")
        return final_response
    
    def _execute_workflow(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the multi-agent workflow"""
        current_agent = 'planning'
        trace = []
        max_steps = 10  # Prevent infinite loops
        step = 0
        
        while current_agent != 'complete' and step < max_steps:
            step += 1
            
            if current_agent == 'human':
                # In a real implementation, this would wait for human input
                trace.append({
                    'step': step,
                    'agent': 'human',
                    'action': 'human_review_required',
                    'timestamp': datetime.now().isoformat()
                })
                break
            
            if current_agent in self.agents:
                agent = self.agents[current_agent]
                
                try:
                    agent_result = agent.process(context)
                    context.update(agent_result)
                    
                    trace.append({
                        'step': step,
                        'agent': current_agent,
                        'action': 'processed',
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    current_agent = agent_result.get('next_agent', 'complete')
                    
                except Exception as e:
                    logger.error(f"Error in agent {current_agent}: {e}")
                    trace.append({
                        'step': step,
                        'agent': current_agent,
                        'action': 'error',
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    })
                    break
            else:
                logger.error(f"Unknown agent: {current_agent}")
                break
        
        # Extract final results
        analysis_result = context.get('analysis_result', {})
        guard_result = context.get('guard_result', {})
        
        return {
            'final_response': guard_result.get('modified_response', analysis_result.get('response', '')),
            'sources': analysis_result.get('sources', []),
            'tool_results': analysis_result.get('tool_results', {}),
            'confidence': analysis_result.get('confidence', 0.0),
            'requires_human_review': guard_result.get('requires_human_review', False),
            'trace': trace
        }
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get conversation history"""
        return self.conversation_history
