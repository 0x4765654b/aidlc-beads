<!-- beads-issue: gt-8 -->
<!-- beads-review: gt-13 -->
# Component Design -- Gorilla Troop

## System Component Map

```mermaid
graph TB
    subgraph gorillaRepo [gorilla-troop/ Repository]
        subgraph orchestratorPkg [orchestrator/]
            Main["main.py\nEntry point"]
            AgentEngine["engine/\nAgent lifecycle management"]
            HarmbeAgent["agents/harmbe/\nSilverback orchestrator"]
            PMAgent["agents/project_minder/\nGraph controller"]
            ChimpAgents["agents/chimps/\n8 stage specialists"]
            CrossAgents["agents/cross_cutting/\nBonobo, Groomer, Snake,\nCurious George, Gibbon"]
            TroopAgent["agents/troop/\nShort-lived workers"]
            ScribeLib["lib/scribe/\nArtifact tool library"]
            BonoboLib["lib/bonobo/\nWrite guard wrappers"]
            ContextLib["lib/context/\nContext dispatch protocol"]
            BeadsLib["lib/beads/\nBeads CLI wrapper"]
            AgentMailLib["lib/agent_mail/\nAgent Mail client"]
        end

        subgraph dashboardPkg [dashboard/]
            FastAPIApp["backend/\nFastAPI app"]
            ReactApp["frontend/\nReact app"]
        end

        subgraph cliPkg [cli/]
            GTCmd["gt command"]
        end

        subgraph infraPkg [infra/]
            DockerCompose["docker-compose.yml"]
            EnvConfig[".env.example"]
            Dockerfiles["Dockerfile.*"]
        end
    end

    subgraph externalSvc [External Services]
        Bedrock["Amazon Bedrock API"]
        AgentMailSvc["MCP Agent Mail\n(Docker container)"]
        OutlineSvc["Outline Wiki\n(Docker container)"]
    end

    Main --> AgentEngine
    AgentEngine --> HarmbeAgent
    AgentEngine --> PMAgent
    PMAgent --> ChimpAgents
    PMAgent --> CrossAgents
    PMAgent --> TroopAgent
    ChimpAgents --> ScribeLib
    ChimpAgents --> BonoboLib
    HarmbeAgent --> AgentMailLib
    PMAgent --> ContextLib
    PMAgent --> BeadsLib
    HarmbeAgent --> Bedrock
    PMAgent --> Bedrock
    ChimpAgents --> Bedrock
    FastAPIApp --> AgentEngine
    GTCmd --> FastAPIApp
