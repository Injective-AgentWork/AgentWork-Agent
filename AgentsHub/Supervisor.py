from typing import Literal
from typing_extensions import TypedDict
from dotenv import load_dotenv
load_dotenv()
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState, END
from langgraph.types import Command
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
# from Crawl_news_agent import *


class State(MessagesState):
    next: str

class Agent:
    def __init__(self,name,description,tools,prompts,llm):

        self.name = name
        self.description = description
        self.tools = tools
        self.prompts = prompts
        self.llm = llm
        
        self.agent = self.create()
        self.agent_node = self.node()
    
    def create(self):
        agent = create_react_agent(self.llm,
                                   tools = self.tools,
                                   prompt = self.prompts,
                                   name = self.name)
        return agent
    
    def node(self):
        agent = self.agent
        name = self.name
        def agent_node(state: State) -> Command[Literal["supervisor"]]:
            result = agent.invoke(state)
            return Command(
            update={
                "messages": [
                    HumanMessage(content=result["messages"][-1].content, name=name)
                ]
            },
            goto="supervisor",
    )
        return agent_node


class Supervise_graph():

    def __init__(self,llm = ChatOpenAI(model = "gpt-4o"), 
                 members = [],
                 member_nodes = [], 
                 job_description ="", 
                 prompt = ""):
        self.members = [member.agent for member in members if  isinstance(member,Agent) ]
        self.member_names = [member.name for member in members if  isinstance(member,Agent)]
        self.member_nodes = member_nodes
        self.job_description = job_description
        
        self.options = members+["FINISH"]
        self.llm = llm
        default_promt = (
    "You are a team supervisor tasked with managing a conversation between the"
    f" following workers: {self.member_names}. Given the following user request,"
    " respond with the worker to act next. Each worker will perform a"
    " task and respond with their results and status."
    "if the input do not contain any tasks, you can response to user and finish"
)
        if prompt is None or len(prompt) == 0:
            self.prompt = default_promt
        else:
            self.prompt = prompt
        # print(self.prompt)
            
        # self.Router.__annotations__["next"] = Literal[*self.options]
        
        self.main_node = self.node()
        self.graph = self.build_graph()
        

    def get_member_names(self):
        return self.member_names
    
    
    def node(self):
        class Router(TypedDict):
            """Worker to route to next. If no workers needed, route to FINISH."""

            next: str
        member_names = self.member_names
        def supervisor_node(state: State) -> Command[Literal[*member_names,"__end__"]]:
            messages = [
                {"role": "system", "content": self.prompt},
            ] + state["messages"]
            print(messages)
            response = self.llm.with_structured_output(Router).invoke(messages)
            print(response)
            goto = response["next"]
            if goto == "FINISH":
                goto = END

            return Command(goto=goto, update={"next": goto})   
        return supervisor_node
    
    def build_graph(self):
        print(type(self.main_node))
        builder = StateGraph(State)
        builder.add_edge(START, "supervisor")
        builder.add_node("supervisor", self.main_node)
        for i in range(len(self.member_nodes)):
            builder.add_node(self.member_names[i],self.member_nodes[i])
        graph = builder.compile()
        return graph
    
    def make_request(self,request,stream=False,save_progress = None):
        progress = []
        if stream==True:
            for s in self.graph.stream(
                {"messages": [("user", 
                            request)]}, subgraphs=True
                ):
                progress.append(s)
                print(s)
                print("----")
        else:
            a = self.graph.invoke({"messages": [("user", 
                            request)]}, subgraphs=True
            )
            if save_progress is not None:
                for sub in a:
                    if len(sub)>0:
                        messages = sub["messages"]
                        for mess in messages:
                            content = mess.content
                            with open(save_progress,"a",encoding='utf8') as file:
                                file.write(content+"\n"+"------"+"\n")
            return a
        if save_progress is not None:
            for s in progress:
                breakpoint()
                if len(s) == 0:
                    continue
                for sub in s:
                    if len(sub)>0:
                        messages = sub["messages"]
                        for mess in messages:
                            content = mess.content
                            with open(save_progress,"w",econding='utf8') as file:
                                file.write(content+"\n"+"----------"+"\n")
            return "-------\n".join(progress)
        
        


if __name__=="__main__":
    llm = ChatOpenAI(model = "gpt-4o-mini")
    a1 = Agent(name="crawler",description="",tools=[],prompts="You are an researcher, use some tools to search and crawl some useful information",llm=llm)
    a2 = Agent(name="Content creater",description="",tools=[],prompts="You are a Content creater. According to the content that was extracted, write for me a post that summary all the news. Then, save that post to my computer",llm=llm)
    a3 = Agent(name="reader",description="",tools=[],prompts="You are a reader, read the content in a specifice url and summary it.",llm=llm)
    agents = [a1,a2,a3]
    super_graph = Supervise_graph(llm=llm,
                                  members = agents,
                                  member_nodes=[a.agent_node for a in agents],
                                  )
    # print(super_graph.prompt)
    
    for i in range(3):
        print(type(super_graph.member_nodes[i]))
    request = """
    This url links to a block that contains many artiles. I need you crawl and summary the information from latest articles of that site.
    After that, summary and write for me a report. You need to crawll all the href first, then visit them to find the information.
    after that, save the summary to my computer
    This is the url: https://blog.injective.com/
    """
    super_graph.make_request(request,stream=False)  
    
    
    
    
    
    
    
    
    