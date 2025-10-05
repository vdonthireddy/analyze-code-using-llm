
"""
Git Repository Security Analyzer using LangChain and LangGraph
Compatible with Python 3.13.1+ and supports Ollama (llama3.2)
"""
import os
import shutil
import sys
from pathlib import Path
from typing import List, Dict, TypedDict, Annotated
import git
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langchain_community.chat_models import ChatOllama
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor
import operator

# Check Python version
if sys.version_info < (3, 8):
    raise RuntimeError("This application requires Python 3.8 or higher. Python 3.13.1+ recommended.")


class AnalysisState(TypedDict):
    """State for the security analysis workflow"""
    repo_url: str
    repo_path: str
    files_to_analyze: List[Dict[str, str]]
    current_file_index: int
    security_findings: Annotated[List[Dict], operator.add]
    summary: str
    error: str


class GitRepoAnalyzer:
    """Main class for analyzing Git repositories for security issues"""
    
    def __init__(self, openai_api_key: str = None, use_azure: bool = None, use_ollama: bool = None,
                 ollama_model: str = None, ollama_base_url: str = None):
        """Initialize the analyzer with OpenAI, Azure OpenAI, or Ollama
        
        Args:
            openai_api_key: OpenAI or Azure API key (not needed for Ollama)
            use_azure: Force use of Azure OpenAI
            use_ollama: Force use of Ollama (local LLM)
            ollama_model: Ollama model name (default: llama3.2)
            ollama_base_url: Ollama server URL (default: http://localhost:11434)
        """
        # Auto-detect which LLM provider to use
        if use_ollama is None:
            use_ollama = bool(os.getenv("USE_OLLAMA", "").lower() in ['true', '1', 'yes'])
        
        if use_azure is None and not use_ollama:
            use_azure = bool(os.getenv("AZURE_OPENAI_API_KEY"))
        
        if use_ollama:
            # Ollama configuration (local LLM)
            ollama_model = ollama_model or os.getenv("OLLAMA_MODEL", "llama3.2")
            ollama_base_url = ollama_base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            
            self.llm = ChatOllama(
                model=ollama_model,
                base_url=ollama_base_url,
                temperature=0
            )
            print(f"✅ Using Ollama (model: {ollama_model}, url: {ollama_base_url})")
            self.api_key = None
            
        elif use_azure:
            # Azure OpenAI configuration
            self.api_key = openai_api_key or os.getenv("AZURE_OPENAI_API_KEY")
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
            api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
            
            if not self.api_key or not azure_endpoint:
                raise ValueError("Azure OpenAI requires AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT environment variables.")
            
            self.llm = AzureChatOpenAI(
                azure_deployment=azure_deployment,
                api_version=api_version,
                azure_endpoint=azure_endpoint,
                api_key=self.api_key,
                temperature=0
            )
            print(f"✅ Using Azure OpenAI (deployment: {azure_deployment})")
        else:
            # Standard OpenAI configuration
            self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError(
                    "OpenAI API key is required. Set OPENAI_API_KEY environment variable "
                    "or use Ollama with USE_OLLAMA=true."
                )
            
            self.llm = ChatOpenAI(
                model="gpt-4",
                temperature=0,
                api_key=self.api_key
            )
            print("✅ Using OpenAI GPT-4")
        
        self.clone_dir = Path("cloned_repos")
        self.clone_dir.mkdir(exist_ok=True)
        
    def clone_repository(self, repo_url: str) -> str:
        """Clone a Git repository to local directory"""
        repo_name = repo_url.rstrip('/').split('/')[-1].replace('.git', '')
        repo_path = self.clone_dir / repo_name
        
        # Remove existing directory if it exists
        if repo_path.exists():
            shutil.rmtree(repo_path)
        
        print(f"Cloning repository: {repo_url}")
        git.Repo.clone_from(repo_url, repo_path)
        print(f"Repository cloned to: {repo_path}")
        
        return str(repo_path)
    
    def get_code_files(self, repo_path: str) -> List[Dict[str, str]]:
        """Get all code files from the repository"""
        code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs',
            '.cpp', '.c', '.h', '.hpp', '.cs', '.php', '.rb', '.swift',
            '.kt', '.scala', '.sh', '.bash', '.yaml', '.yml', '.json',
            '.sql', '.html', '.css'
        }
        
        files = []
        repo_path_obj = Path(repo_path)
        
        for file_path in repo_path_obj.rglob('*'):
            # Skip hidden directories and common non-code directories
            if any(part.startswith('.') for part in file_path.parts):
                continue
            if any(part in ['node_modules', 'venv', '__pycache__', 'dist', 'build'] 
                   for part in file_path.parts):
                continue
            
            if file_path.is_file() and file_path.suffix in code_extensions:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Skip very large files (> 50KB)
                    if len(content) > 50000:
                        continue
                    
                    files.append({
                        'path': str(file_path.relative_to(repo_path_obj)),
                        'content': content,
                        'extension': file_path.suffix
                    })
                except (UnicodeDecodeError, PermissionError):
                    continue
        
        print(f"Found {len(files)} code files to analyze")
        return files
    
    def analyze_file_for_security(self, file_info: Dict[str, str]) -> Dict:
        """Analyze a single file for security issues using LLM"""
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a security expert analyzing code for vulnerabilities.
            Identify security issues including but not limited to:
            - SQL Injection vulnerabilities
            - Cross-Site Scripting (XSS)
            - Command Injection
            - Path Traversal
            - Insecure Deserialization
            - Hardcoded credentials or secrets
            - Weak cryptography
            - Authentication/Authorization issues
            - Insecure dependencies
            - Information disclosure
            - CSRF vulnerabilities
            - Insecure configurations
            
            For each issue found, provide:
            1. Severity (Critical, High, Medium, Low)
            2. Description of the issue
            3. Line number or code snippet
            4. Recommendation for fixing
            
            If no issues are found, respond with "No security issues detected."
            Be specific and actionable in your findings."""),
            HumanMessage(content=f"""Analyze this file for security vulnerabilities:

File: {file_info['path']}
Extension: {file_info['extension']}

Code:
```
{file_info['content']}
```

Provide your analysis in a structured format.""")
        ])
        
        try:
            response = self.llm.invoke(prompt.format_messages())
            
            return {
                'file': file_info['path'],
                'analysis': response.content,
                'has_issues': 'No security issues detected' not in response.content
            }
        except Exception as e:
            return {
                'file': file_info['path'],
                'analysis': f"Error analyzing file: {str(e)}",
                'has_issues': False
            }
    
    def generate_summary(self, findings: List[Dict]) -> str:
        """Generate a summary of all security findings"""
        files_with_issues = [f for f in findings if f.get('has_issues', False)]
        
        if not files_with_issues:
            return "No security issues detected in the repository."
        
        # Build findings text outside of f-string to avoid backslash issues
        findings_text = "\n".join([f"File: {f['file']}\n{f['analysis']}\n" for f in files_with_issues])
        
        summary_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a security analyst creating an executive summary.
            Summarize the security findings across multiple files, highlighting:
            1. Total number of files with issues
            2. Most critical vulnerabilities found
            3. Common patterns or themes
            4. Priority recommendations
            
            Keep the summary concise but informative."""),
            HumanMessage(content=f"""Create a summary of these security findings:

{findings_text}

Provide an executive summary.""")
        ])
        
        try:
            response = self.llm.invoke(summary_prompt.format_messages())
            return response.content
        except Exception as e:
            return f"Error generating summary: {str(e)}"
    
    def analyze_code_complexity(self, file_info: Dict[str, str]) -> Dict:
        """Analyze code complexity, maintainability, and quality metrics"""
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a senior software architect and code quality expert.
            Analyze the code for complexity and maintainability metrics including:
            
            1. **Cyclomatic Complexity**: Measure of code complexity based on control flow
               - Low (1-10): Simple, easy to test
               - Moderate (11-20): More complex, needs attention
               - High (21-50): Complex, difficult to maintain
               - Very High (50+): Extremely complex, refactor recommended
            
            2. **Cognitive Complexity**: How difficult the code is to understand
               - Nested loops, conditionals, recursion
               - Code readability and mental overhead
            
            3. **Code Smells**: Identify anti-patterns and issues
               - Long methods/functions (>50 lines)
               - Large classes (>300 lines)
               - Too many parameters (>5)
               - Deep nesting (>4 levels)
               - Duplicate code
               - Dead code
               - Magic numbers
               - Poor naming conventions
            
            4. **Maintainability Index**: Overall maintainability score
               - High (80-100): Highly maintainable
               - Moderate (50-79): Moderately maintainable
               - Low (0-49): Difficult to maintain
            
            5. **Technical Debt**: Areas requiring refactoring
               - Estimated effort to fix
               - Priority level
            
            6. **Best Practices**: Adherence to coding standards
               - SOLID principles
               - DRY (Don't Repeat Yourself)
               - KISS (Keep It Simple)
               - Proper error handling
               - Documentation quality
            
            7. **Dependencies**: Coupling and cohesion analysis
               - Tight coupling issues
               - Low cohesion problems
            
            For each metric, provide:
            - Score/Rating
            - Specific examples from the code
            - Recommendations for improvement
            - Priority (High/Medium/Low)
            
            If the code is well-written, acknowledge it and provide minor suggestions.
            Be specific with line numbers and code snippets when possible."""),
            HumanMessage(content=f"""Analyze the complexity and quality of this code:

File: {file_info['path']}
Extension: {file_info['extension']}
Lines of Code: {len(file_info['content'].splitlines())}

Code:
```
{file_info['content']}
```

Provide a comprehensive complexity analysis with:
1. Overall complexity rating (Low/Moderate/High/Very High)
2. Cyclomatic complexity estimate
3. Cognitive complexity assessment
4. Code smells identified
5. Maintainability index estimate
6. Technical debt items
7. Specific recommendations for improvement
8. Priority areas to address

Format your response in a clear, structured manner.""")
        ])
        
        try:
            response = self.llm.invoke(prompt.format_messages())
            
            return {
                'file': file_info['path'],
                'complexity_analysis': response.content,
                'lines_of_code': len(file_info['content'].splitlines()),
                'file_size': len(file_info['content'])
            }
        except Exception as e:
            return {
                'file': file_info['path'],
                'complexity_analysis': f"Error analyzing complexity: {str(e)}",
                'lines_of_code': len(file_info['content'].splitlines()),
                'file_size': len(file_info['content'])
            }
    
    def generate_complexity_summary(self, complexity_results: List[Dict]) -> str:
        """Generate a summary of code complexity analysis across all files"""
        if not complexity_results:
            return "No complexity analysis results available."
        
        # Build complexity text
        complexity_text = "\n".join([
            f"File: {r['file']}\nLines: {r['lines_of_code']}\n{r['complexity_analysis']}\n"
            for r in complexity_results
        ])
        
        summary_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a software architect creating an executive summary of code complexity analysis.
            
            Summarize the complexity findings across all files, highlighting:
            1. Overall codebase complexity level (Low/Moderate/High/Very High)
            2. Total lines of code analyzed
            3. Most complex files requiring immediate attention
            4. Common complexity patterns and anti-patterns
            5. Technical debt hotspots
            6. Maintainability concerns
            7. Priority recommendations for refactoring
            8. Estimated effort for improvements (High/Medium/Low)
            9. Positive aspects of the codebase
            
            Provide actionable insights and prioritize recommendations.
            Keep the summary comprehensive but concise."""),
            HumanMessage(content=f"""Create an executive summary of these complexity analyses:

{complexity_text}

Provide a comprehensive summary with:
- Overall assessment
- Key findings
- Priority recommendations
- Estimated refactoring effort""")
        ])
        
        try:
            response = self.llm.invoke(summary_prompt.format_messages())
            return response.content
        except Exception as e:
            return f"Error generating complexity summary: {str(e)}"
    
    def analyze_repository_complexity(self, repo_url: str) -> Dict:
        """Analyze code complexity for entire repository"""
        print(f"\n{'='*60}")
        print(f"Starting complexity analysis of: {repo_url}")
        print(f"{'='*60}\n")
        
        # Clone repository
        try:
            repo_path = self.clone_repository(repo_url)
        except Exception as e:
            return {
                'error': f"Error cloning repository: {str(e)}",
                'repo_url': repo_url
            }
        
        # Get code files
        try:
            files = self.get_code_files(repo_path)
        except Exception as e:
            return {
                'error': f"Error collecting files: {str(e)}",
                'repo_url': repo_url
            }
        
        if not files:
            return {
                'repo_url': repo_url,
                'files_analyzed': 0,
                'complexity_results': [],
                'summary': 'No code files found to analyze.',
                'error': ''
            }
        
        # Analyze each file for complexity
        complexity_results = []
        total_files = len(files)
        
        print(f"Analyzing complexity of {total_files} files...\n")
        
        for idx, file_info in enumerate(files, 1):
            print(f"Analyzing file {idx}/{total_files}: {file_info['path']}")
            result = self.analyze_code_complexity(file_info)
            complexity_results.append(result)
        
        # Generate summary
        print("\nGenerating complexity summary...")
        summary = self.generate_complexity_summary(complexity_results)
        
        # Calculate statistics
        total_lines = sum(r['lines_of_code'] for r in complexity_results)
        avg_lines = total_lines // len(complexity_results) if complexity_results else 0
        
        return {
            'repo_url': repo_url,
            'files_analyzed': len(complexity_results),
            'total_lines_of_code': total_lines,
            'average_lines_per_file': avg_lines,
            'complexity_results': complexity_results,
            'summary': summary,
            'error': ''
        }
    
    def build_analysis_graph(self) -> StateGraph:
        """Build the LangGraph workflow for security analysis"""
        
        def clone_repo_node(state: AnalysisState) -> AnalysisState:
            """Node to clone the repository"""
            try:
                repo_path = self.clone_repository(state['repo_url'])
                state['repo_path'] = repo_path
                state['error'] = ''
            except Exception as e:
                state['error'] = f"Error cloning repository: {str(e)}"
            return state
        
        def collect_files_node(state: AnalysisState) -> AnalysisState:
            """Node to collect code files"""
            if state.get('error'):
                return state
            
            try:
                files = self.get_code_files(state['repo_path'])
                state['files_to_analyze'] = files
                state['current_file_index'] = 0
                state['security_findings'] = []
            except Exception as e:
                state['error'] = f"Error collecting files: {str(e)}"
            return state
        
        def analyze_file_node(state: AnalysisState) -> AnalysisState:
            """Node to analyze a single file"""
            if state.get('error') or not state['files_to_analyze']:
                return state
            
            idx = state['current_file_index']
            if idx < len(state['files_to_analyze']):
                file_info = state['files_to_analyze'][idx]
                print(f"Analyzing file {idx + 1}/{len(state['files_to_analyze'])}: {file_info['path']}")
                
                finding = self.analyze_file_for_security(file_info)
                state['security_findings'] = [finding]
                state['current_file_index'] = idx + 1
            
            return state
        
        def should_continue_analysis(state: AnalysisState) -> str:
            """Decide whether to continue analyzing files"""
            if state.get('error'):
                return "summarize"
            
            if state['current_file_index'] < len(state['files_to_analyze']):
                return "analyze_more"
            else:
                return "summarize"
        
        def summarize_node(state: AnalysisState) -> AnalysisState:
            """Node to generate summary"""
            if state.get('error'):
                state['summary'] = f"Analysis failed: {state['error']}"
                return state
            
            print("\nGenerating summary...")
            state['summary'] = self.generate_summary(state['security_findings'])
            return state
        
        # Build the graph
        workflow = StateGraph(AnalysisState)
        
        # Add nodes
        workflow.add_node("clone_repo", clone_repo_node)
        workflow.add_node("collect_files", collect_files_node)
        workflow.add_node("analyze_file", analyze_file_node)
        workflow.add_node("summarize", summarize_node)
        
        # Add edges
        workflow.set_entry_point("clone_repo")
        workflow.add_edge("clone_repo", "collect_files")
        workflow.add_edge("collect_files", "analyze_file")
        workflow.add_conditional_edges(
            "analyze_file",
            should_continue_analysis,
            {
                "analyze_more": "analyze_file",
                "summarize": "summarize"
            }
        )
        workflow.add_edge("summarize", END)
        
        return workflow.compile()
    
    def analyze_repository(self, repo_url: str) -> Dict:
        """Main method to analyze a repository"""
        print(f"\n{'='*60}")
        print(f"Starting security analysis of: {repo_url}")
        print(f"{'='*60}\n")
        
        # Build and run the graph
        graph = self.build_analysis_graph()
        
        initial_state: AnalysisState = {
            'repo_url': repo_url,
            'repo_path': '',
            'files_to_analyze': [],
            'current_file_index': 0,
            'security_findings': [],
            'summary': '',
            'error': ''
        }
        
        final_state = graph.invoke(initial_state)
        
        return {
            'repo_url': repo_url,
            'files_analyzed': len(final_state['files_to_analyze']),
            'findings': final_state['security_findings'],
            'summary': final_state['summary'],
            'error': final_state.get('error', '')
        }


def main():
    """Main function to run the analyzer"""
    from dotenv import load_dotenv
    load_dotenv()
    
    # Initialize analyzer
    analyzer = GitRepoAnalyzer()
    
    # Analyze the specified repository
    repo_url = "https://github.com/vdonthireddy/spark-scala-minio-delta.git"
    results = analyzer.analyze_repository(repo_url)
    
    # Print results
    print(f"\n{'='*60}")
    print("ANALYSIS RESULTS")
    print(f"{'='*60}\n")
    
    if results['error']:
        print(f"Error: {results['error']}")
    else:
        print(f"Repository: {results['repo_url']}")
        print(f"Files Analyzed: {results['files_analyzed']}")
        print(f"\n{'='*60}")
        print("EXECUTIVE SUMMARY")
        print(f"{'='*60}\n")
        print(results['summary'])
        
        print(f"\n{'='*60}")
        print("DETAILED FINDINGS")
        print(f"{'='*60}\n")
        
        for finding in results['findings']:
            if finding.get('has_issues'):
                print(f"\n📁 File: {finding['file']}")
                print("-" * 60)
                print(finding['analysis'])
                print()

    """Analyze repository for code complexity"""
    
    print("="*80)
    print("CODE COMPLEXITY ANALYZER")
    print("="*80)
    print(f"\n📦 Repository: {repo_url}\n")
    
    try:
        # Initialize analyzer
        print("🔧 Initializing analyzer...")
        analyzer = GitRepoAnalyzer()
        
        # Analyze complexity
        print(f"\n🔍 Analyzing code complexity...\n")
        results = analyzer.analyze_repository_complexity(repo_url)
        
        # Check for errors
        if results.get('error'):
            print(f"\n❌ Error: {results['error']}")
            sys.exit(1)
        
        # Display summary
        print("\n" + "="*80)
        print("📊 COMPLEXITY ANALYSIS SUMMARY")
        print("="*80)
        print(f"\n✅ Files Analyzed: {results['files_analyzed']}")
        print(f"📝 Total Lines of Code: {results['total_lines_of_code']:,}")
        print(f"📄 Average Lines per File: {results['average_lines_per_file']}")
        
        # Executive Summary
        print("\n" + "="*80)
        print("📋 EXECUTIVE SUMMARY")
        print("="*80)
        print(f"\n{results['summary']}\n")
        
        # Detailed Complexity Analysis
        print("="*80)
        print("🔍 DETAILED COMPLEXITY ANALYSIS BY FILE")
        print("="*80)
        
        for idx, result in enumerate(results['complexity_results'], 1):
            print(f"\n{'─'*80}")
            print(f"File #{idx}: {result['file']}")
            print(f"Lines of Code: {result['lines_of_code']}")
            print(f"{'─'*80}")
            print(result['complexity_analysis'])
            print()
        
        # Save report
        report_file = "complexity_analysis_report.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("CODE COMPLEXITY ANALYSIS REPORT\n")
            f.write("="*80 + "\n\n")
            f.write(f"Repository: {repo_url}\n")
            f.write(f"Files Analyzed: {results['files_analyzed']}\n")
            f.write(f"Total Lines of Code: {results['total_lines_of_code']:,}\n")
            f.write(f"Average Lines per File: {results['average_lines_per_file']}\n\n")
            f.write("="*80 + "\n")
            f.write("EXECUTIVE SUMMARY\n")
            f.write("="*80 + "\n\n")
            f.write(results['summary'] + "\n\n")
            f.write("="*80 + "\n")
            f.write("DETAILED COMPLEXITY ANALYSIS\n")
            f.write("="*80 + "\n\n")
            
            for idx, result in enumerate(results['complexity_results'], 1):
                f.write(f"\nFile #{idx}: {result['file']}\n")
                f.write(f"Lines of Code: {result['lines_of_code']}\n")
                f.write("-"*80 + "\n")
                f.write(result['complexity_analysis'] + "\n\n")
        
        print(f"\n💾 Report saved to: {report_file}")
        print("\n" + "="*80)
        print("✅ COMPLEXITY ANALYSIS COMPLETE")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
