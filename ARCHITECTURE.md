# CanvasDrawer Fullstack System Architecture

This document provides a comprehensive structural and data-flow map of the collaborative whiteboard platform, covering the **Frontend Engine**, the **Nginx Load Balancer**, the **3-Replica Django Backend**, and the **Data & Synchronization Layers**.

---

## 1. High-Level End-to-End Architecture

```mermaid
flowchart TB
    subgraph Frontend["Frontend Client (React + TypeScript + Canvas)"]
        UI["UI Layer\n(Dashboard, Canvas, Auth Modal, Toolbar)"]
        Hook["Reactive Hook\n(useWhiteboard)"]
        Core["Canvas Engine\n(Whiteboard Facade, Drawer, Renderer, Viewport)"]
        Sync["SyncClient\n(WebSocket Protocol, Reconnects, Cursor, Ops)"]
        UI <--> Hook
        Hook <--> Core
        Core <--> Sync
    end

    subgraph Gateway["Traffic Gateway & Load Balancer"]
        Nginx["Nginx Reverse Proxy & Load Balancer (:80)\nip_hash sticky session + WebSocket upgrade"]
    end

    Sync -->|ws://host/ws/?inviteCode=...| Nginx
    UI -->|http://host/api/...| Nginx

    subgraph Cluster["High-Availability 3-Replica Backend Cluster"]
        B1["backend-1:8000\n(Daphne ASGI + Django)"]
        B2["backend-2:8000\n(Daphne ASGI + Django)"]
        B3["backend-3:8000\n(Daphne ASGI + Django)"]
    end

    Nginx -->|Load Balanced| B1
    Nginx -->|Load Balanced| B2
    Nginx -->|Load Balanced| B3

    subgraph PersistenceAndSync["Distributed State & Storage"]
        Redis[("Redis 7 (:6379)\nChannels Pub/Sub Layer\nCross-Replica Sync")]
        Postgres[("PostgreSQL 16 (:5432)\nUsers, Whiteboards,\nVersions & Snapshots")]
    end

    B1 <-->|Pub/Sub Channel Layer| Redis
    B2 <-->|Pub/Sub Channel Layer| Redis
    B3 <-->|Pub/Sub Channel Layer| Redis

    B1 <-->|ORM Durable Storage| Postgres
    B2 <-->|ORM Durable Storage| Postgres
    B3 <-->|ORM Durable Storage| Postgres
```

---

## 2. Detailed Frontend Architecture (`Drawer`)

```mermaid
flowchart TD
    subgraph ViewLayer["Presentation Layer (React UI)"]
        App["App.tsx\nSession & Auth State"]
        Dash["Dashboard.tsx\nWhiteboard List, SVG Previews,\nJoin Modal, Auth Modal"]
        CanvasUI["WhiteboardCanvas.tsx\nHTML5 Canvas Mount, Top Bar,\nInvite Code Pill, Viewport HUD"]
        Tools["Toolbar.tsx & ShapePicker.tsx\nActive Tool, Color/Fill, Undo/Redo"]
        App --> Dash
        App --> CanvasUI
        CanvasUI --> Tools
    end

    subgraph StateHook["Reactive Bridge"]
        UseWB["useWhiteboard.ts\nEvent Subscriptions (tool, change, selection, viewport, syncStatus)"]
        CanvasUI <--> UseWB
    end

    subgraph CoreEngine["Canvas Engine Core (src/core/)"]
        WBFacade["Whiteboard.ts (Facade Orchestrator)"]
        DrawerObj["Drawer.ts (Canvas Controller)"]
        
        subgraph SubServices["Specialized Subservices"]
            Renderer["Renderer.ts\nDrawing Pass & Double Buffering"]
            Viewport["ViewportService.ts\nPan, Zoom Matrix, World/Screen Math"]
            Selection["SelectionService.ts\nHit-Testing & Multi-Select Bounds"]
            History["HistoryService.ts\nUndo & Redo Command Stacks"]
            HitTester["HitTester.ts\nPoint & Intersect Geometry"]
        end

        subgraph Shapes["Shapes Domain"]
            Factory["ShapeFactory.ts"]
            ShapeClasses["BaseShape / Rectangle / Circle /\nLine / Triangle / Freehand"]
            Factory --> ShapeClasses
        end

        subgraph Interaction["Cursor & Tools"]
            CursorService["Cursor.ts"]
            ToolClasses["SelectTool / PanTool /\nDrawTool / TransformTool"]
            SnapMath["snapMath.ts (Smart Snapping)"]
            CursorService --> ToolClasses
            ToolClasses --> SnapMath
        end

        UseWB <--> WBFacade
        WBFacade --> DrawerObj
        DrawerObj --> SubServices
        WBFacade --> Shapes
        WBFacade --> Interaction
    end

    subgraph Communication["Network Synchronization Layer"]
        OpService["OperationService.ts\nOp Packaging & Local Snapshot"]
        SyncClient["SyncClient.ts\nWebSocket Transport, Backoff Reconnect,\nCursor Broadcast, Invite Code Check"]
        WBFacade <--> OpService
        OpService <--> SyncClient
    end
```

---

## 3. Detailed Backend Architecture (`CanvasDrawerProject`)

```mermaid
flowchart TD
    subgraph Entrypoint["ASGI / HTTP Ingestion"]
        Daphne["Daphne ASGI Server (:8000)"]
        Middleware["BasicAuthMiddleware\nExtracts HTTP Basic Auth / Session"]
        Router["ProtocolTypeRouter\n(HTTP -> Django Views | WS -> Consumers)"]
        Daphne --> Middleware --> Router
    end

    subgraph RESTLayer["REST API Layer (Dashboard App)"]
        AuthViews["auth_views\n/api/dashboard/auth/login/\n/api/dashboard/auth/register/\n/api/dashboard/auth/logout/\n/api/dashboard/me/"]
        BoardViews["whiteboard_views\n/api/dashboard/whiteboards/\n/api/dashboard/whiteboards/join/\n/api/dashboard/whiteboards/<id>/"]
        VersionViews["version_views\n/api/dashboard/whiteboards/<id>/versions/\n/api/dashboard/whiteboards/<id>/restore/<ver>/"]
        Router -->|HTTP /api/| RESTLayer
    end

    subgraph WSLayer["WebSocket Real-Time Layer (WebSockets App)"]
        Consumer["CanvasConsumer (AsyncWebsocketConsumer)\n- Handshake & extract_invite_code\n- Room group_add(board_<id>)\n- Broadcast distribution\n- Session closure snapshot save"]
        Router -->|WS /ws/| Consumer

        subgraph WSServices["Domain Services"]
            WBSvc["WhiteboardService\nRoom resolution, validation,\naccess check via invite code"]
            ShapeSvc["ShapeService\nIn-memory active board shapes,\nversion mutations"]
            Types["types.py (Protocol Messages)\nsnapshot, shape:add, shape:update, cursor:move"]
        end

        Consumer <--> WBSvc
        WBSvc <--> ShapeSvc
        WBSvc <--> Types
    end

    subgraph EngineLayer["Database Engine Facade (DatabaseEngine)"]
        EngineFacade["DatabaseEngine (Engine.py)\nCentralized sync & async bridge"]
        Repo["WhiteboardRepository\nCRUD, .select_related('owner'),\nverify_access, rollback, snapshot saves"]
        SessionMgr["SessionManager\nActive in-memory channel participants"]
        UserSvc["UserService\nIdentity resolution (Auth vs Guest)"]

        RESTLayer <--> EngineFacade
        Consumer <--> EngineFacade
        WBSvc <--> EngineFacade
        EngineFacade --> Repo
        EngineFacade --> SessionMgr
        EngineFacade --> UserSvc
    end

    subgraph ORMModels["Django ORM Models"]
        WbModel["Whiteboard Model\nid, title, invite_code (unique),\nowner (FK User), snapshot (JSONField),\nversion, last_closed_at"]
        VerModel["WhiteboardVersion Model\nid (UUID), whiteboard (FK),\nversion_number, snapshot (JSONField),\nsaved_by, note"]
        UserModel["Django auth.User Model\nusername, password, email"]

        Repo <--> WbModel
        Repo <--> VerModel
        UserSvc <--> UserModel
    end
```

---

## 4. Real-Time Collaboration & Invitation Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Host as Host (Client A)
    actor Guest as Collaborator (Client B)
    participant Nginx as Nginx Load Balancer
    participant B1 as backend-1
    participant B2 as backend-2
    participant Redis as Redis Pub/Sub
    participant DB as PostgreSQL

    Host->>Nginx: POST /api/dashboard/whiteboards/ { title: "Architecture" }
    Nginx->>B1: Forward request
    B1->>DB: Insert Whiteboard (generates invite_code: "9B2F-4A7C")
    B1-->>Host: 201 Created { id: "board-1", invite_code: "9B2F-4A7C" }

    Host->>Nginx: WS Connect /ws/canvas/board-1/?inviteCode=9B2F-4A7C
    Nginx->>B1: Upgrade WS connection
    B1->>DB: Validate invite code / owner
    B1->>Redis: group_add("board_board-1")
    B1-->>Host: Initial Snapshot { shapes: [], version: 0 }

    Note over Host,Guest: Host shares invite code "9B2F-4A7C" with Collaborator

    Guest->>Nginx: POST /api/dashboard/whiteboards/join/ { invite_code: "9B2F-4A7C" }
    Nginx->>B2: Forward join request
    B2->>DB: Query by invite_code
    B2-->>Guest: 200 OK { id: "board-1", title: "Architecture" }

    Guest->>Nginx: WS Connect /ws/canvas/board-1/?inviteCode=9B2F-4A7C
    Nginx->>B2: Upgrade WS connection (routed to replica B2)
    B2->>DB: Validate invite code
    B2->>Redis: group_add("board_board-1")
    B2-->>Guest: Initial Snapshot

    Note over Host,Guest: Real-Time Cross-Replica Sync

    Host->>B1: WS Op: { type: "shape:add", shape: { type: "rectangle", ... } }
    B1->>Redis: Publish to group "board_board-1"
    Redis-->>B2: Broadcast message to group subscribers
    B2-->>Guest: Forward Op: { type: "shape:add", shape: { ... } }
```

