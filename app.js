const START_TIME_SECONDS = 10 * 60;
const PIECE_ORDER = ["K", "Q", "R", "B", "N", "P"];
const PIECE_NAMES = {
    K: "Rey",
    Q: "Reina",
    R: "Torre",
    B: "Alfil",
    N: "Caballo",
    P: "Peon",
};

class ChessGame {
    constructor() {
        this.reset();
    }

    reset() {
        this.board = [
            ["r", "n", "b", "q", "k", "b", "n", "r"],
            ["p", "p", "p", "p", "p", "p", "p", "p"],
            [null, null, null, null, null, null, null, null],
            [null, null, null, null, null, null, null, null],
            [null, null, null, null, null, null, null, null],
            [null, null, null, null, null, null, null, null],
            ["P", "P", "P", "P", "P", "P", "P", "P"],
            ["R", "N", "B", "Q", "K", "B", "N", "R"],
        ];
        this.turn = "w";
        this.selected = null;
        this.legalTargets = [];
        this.history = [];
        this.lastMove = null;
        this.enPassantTarget = null;
        this.castling = { K: true, Q: true, k: true, q: true };
        this.flipped = false;
        this.status = "Juegan blancas";
        this.pendingSound = "game-start";
        this.clocks = { w: START_TIME_SECONDS, b: START_TIME_SECONDS };
        this.lowTimeWarning = { w: false, b: false };
        this.hiddenSquare = null;
    }

    colorOf(piece) {
        if (!piece) return null;
        return piece === piece.toUpperCase() ? "w" : "b";
    }

    opposite(color) {
        return color === "w" ? "b" : "w";
    }

    inBounds(row, col) {
        return row >= 0 && row < 8 && col >= 0 && col < 8;
    }

    handleSquareClick(square) {
        if (this.gameOver()) return null;
        const [row, col] = square;
        const piece = this.board[row][col];
        const hadSelection = Boolean(this.selected);
        const chosen = this.legalTargets.find((move) => sameSquare(move.end, square));

        if (chosen) {
            this.pushMove(chosen);
            return chosen;
        }

        if (piece && this.colorOf(piece) === this.turn) {
            this.selected = square;
            this.legalTargets = this.legalMovesFrom(square);
            return null;
        }

        this.selected = null;
        this.legalTargets = [];
        if (hadSelection || piece) {
            this.pendingSound = "illegal";
        }
        return null;
    }

    legalMovesFrom(square) {
        return this.allLegalMoves(this.turn).filter((move) => sameSquare(move.start, square));
    }

    allLegalMoves(color) {
        const moves = [];
        for (let row = 0; row < 8; row += 1) {
            for (let col = 0; col < 8; col += 1) {
                const piece = this.board[row][col];
                if (piece && this.colorOf(piece) === color) {
                    for (const move of this.pseudoMoves([row, col], true)) {
                        if (!this.leavesKingInCheck(move, color)) {
                            moves.push(move);
                        }
                    }
                }
            }
        }
        return moves;
    }

    pseudoMoves(square, includeCastles = false) {
        const [row, col] = square;
        const piece = this.board[row][col];
        if (!piece) return [];
        const color = this.colorOf(piece);
        const enemy = this.opposite(color);
        const kind = piece.toUpperCase();
        const moves = [];

        if (kind === "P") {
            const direction = color === "w" ? -1 : 1;
            const startRow = color === "w" ? 6 : 1;
            const promotionRow = color === "w" ? 0 : 7;
            const nextRow = row + direction;

            if (this.inBounds(nextRow, col) && !this.board[nextRow][col]) {
                moves.push(createMove(square, [nextRow, col], piece, null, nextRow === promotionRow ? (color === "w" ? "Q" : "q") : null));
                const jumpRow = row + direction * 2;
                if (row === startRow && !this.board[jumpRow][col]) {
                    moves.push(createMove(square, [jumpRow, col], piece));
                }
            }

            for (const deltaCol of [-1, 1]) {
                const targetCol = col + deltaCol;
                if (!this.inBounds(nextRow, targetCol)) continue;
                const target = this.board[nextRow][targetCol];
                if (target && this.colorOf(target) === enemy) {
                    moves.push(createMove(square, [nextRow, targetCol], piece, target, nextRow === promotionRow ? (color === "w" ? "Q" : "q") : null));
                }
                if (this.enPassantTarget && sameSquare(this.enPassantTarget, [nextRow, targetCol])) {
                    moves.push({
                        ...createMove(square, [nextRow, targetCol], piece, color === "w" ? "p" : "P"),
                        enPassant: true,
                    });
                }
            }
        } else if (kind === "N") {
            const offsets = [[-2, -1], [-2, 1], [-1, -2], [-1, 2], [1, -2], [1, 2], [2, -1], [2, 1]];
            for (const [deltaRow, deltaCol] of offsets) {
                this.addStepMove(moves, square, row + deltaRow, col + deltaCol, piece);
            }
        } else if (kind === "B" || kind === "R" || kind === "Q") {
            const directions = [];
            if (kind === "B" || kind === "Q") directions.push([-1, -1], [-1, 1], [1, -1], [1, 1]);
            if (kind === "R" || kind === "Q") directions.push([-1, 0], [1, 0], [0, -1], [0, 1]);
            for (const [deltaRow, deltaCol] of directions) {
                this.addSlideMoves(moves, square, deltaRow, deltaCol, piece);
            }
        } else if (kind === "K") {
            for (let deltaRow = -1; deltaRow <= 1; deltaRow += 1) {
                for (let deltaCol = -1; deltaCol <= 1; deltaCol += 1) {
                    if (!deltaRow && !deltaCol) continue;
                    this.addStepMove(moves, square, row + deltaRow, col + deltaCol, piece);
                }
            }
            if (includeCastles && !this.isInCheck(color)) {
                this.addCastleMoves(moves, square, piece);
            }
        }

        return moves;
    }

    addStepMove(moves, start, row, col, piece) {
        if (!this.inBounds(row, col)) return;
        const target = this.board[row][col];
        if (!target || this.colorOf(target) !== this.colorOf(piece)) {
            moves.push(createMove(start, [row, col], piece, target));
        }
    }

    addSlideMoves(moves, start, deltaRow, deltaCol, piece) {
        let [row, col] = start;
        row += deltaRow;
        col += deltaCol;
        while (this.inBounds(row, col)) {
            const target = this.board[row][col];
            if (!target) {
                moves.push(createMove(start, [row, col], piece));
            } else {
                if (this.colorOf(target) !== this.colorOf(piece)) {
                    moves.push(createMove(start, [row, col], piece, target));
                }
                break;
            }
            row += deltaRow;
            col += deltaCol;
        }
    }

    addCastleMoves(moves, square, piece) {
        const color = this.colorOf(piece);
        const row = color === "w" ? 7 : 0;
        const [kingKey, queenKey] = color === "w" ? ["K", "Q"] : ["k", "q"];
        if (!sameSquare(square, [row, 4])) return;

        if (this.castling[kingKey] && !this.board[row][5] && !this.board[row][6]) {
            if (!this.squareAttacked([row, 5], this.opposite(color)) && !this.squareAttacked([row, 6], this.opposite(color))) {
                moves.push({ ...createMove(square, [row, 6], piece), castle: true });
            }
        }

        if (this.castling[queenKey] && !this.board[row][1] && !this.board[row][2] && !this.board[row][3]) {
            if (!this.squareAttacked([row, 3], this.opposite(color)) && !this.squareAttacked([row, 2], this.opposite(color))) {
                moves.push({ ...createMove(square, [row, 2], piece), castle: true });
            }
        }
    }

    snapshot() {
        return {
            board: this.board.map((line) => [...line]),
            enPassantTarget: this.enPassantTarget ? [...this.enPassantTarget] : null,
            castling: { ...this.castling },
            lastMove: this.lastMove ? cloneMove(this.lastMove) : null,
        };
    }

    restore(snapshot) {
        this.board = snapshot.board.map((line) => [...line]);
        this.enPassantTarget = snapshot.enPassantTarget ? [...snapshot.enPassantTarget] : null;
        this.castling = { ...snapshot.castling };
        this.lastMove = snapshot.lastMove ? cloneMove(snapshot.lastMove) : null;
    }

    leavesKingInCheck(move, color) {
        const snapshot = this.snapshot();
        this.applyMove(move);
        const checked = this.isInCheck(color);
        this.restore(snapshot);
        return checked;
    }

    kingSquare(color) {
        const king = color === "w" ? "K" : "k";
        for (let row = 0; row < 8; row += 1) {
            for (let col = 0; col < 8; col += 1) {
                if (this.board[row][col] === king) return [row, col];
            }
        }
        return null;
    }

    isInCheck(color) {
        const king = this.kingSquare(color);
        return king ? this.squareAttacked(king, this.opposite(color)) : false;
    }

    squareAttacked(square, byColor) {
        for (let row = 0; row < 8; row += 1) {
            for (let col = 0; col < 8; col += 1) {
                const piece = this.board[row][col];
                if (piece && this.colorOf(piece) === byColor) {
                    if (this.attacksSquare([row, col], square)) {
                        return true;
                    }
                }
            }
        }
        return false;
    }

    attacksSquare(start, target) {
        const [row, col] = start;
        const [targetRow, targetCol] = target;
        const piece = this.board[row][col];
        if (!piece) return false;
        const color = this.colorOf(piece);
        const kind = piece.toUpperCase();

        if (kind === "P") {
            const direction = color === "w" ? -1 : 1;
            return sameSquare([row + direction, col - 1], target) || sameSquare([row + direction, col + 1], target);
        }
        if (kind === "N") {
            const deltaRow = Math.abs(targetRow - row);
            const deltaCol = Math.abs(targetCol - col);
            return (deltaRow === 1 && deltaCol === 2) || (deltaRow === 2 && deltaCol === 1);
        }
        if (kind === "K") {
            return Math.max(Math.abs(targetRow - row), Math.abs(targetCol - col)) === 1;
        }
        if (kind === "B" || kind === "R" || kind === "Q") {
            const deltaRow = targetRow - row;
            const deltaCol = targetCol - col;
            const stepRow = deltaRow === 0 ? 0 : Math.sign(deltaRow);
            const stepCol = deltaCol === 0 ? 0 : Math.sign(deltaCol);
            const diagonal = Math.abs(deltaRow) === Math.abs(deltaCol);
            const straight = deltaRow === 0 || deltaCol === 0;
            if (kind === "B" && !diagonal) return false;
            if (kind === "R" && !straight) return false;
            if (kind === "Q" && !diagonal && !straight) return false;
            let currentRow = row + stepRow;
            let currentCol = col + stepCol;
            while (currentRow !== targetRow || currentCol !== targetCol) {
                if (this.board[currentRow][currentCol]) return false;
                currentRow += stepRow;
                currentCol += stepCol;
            }
            return true;
        }
        return false;
    }

    pushMove(move) {
        const movingColor = this.turn;
        this.hiddenSquare = move.end;
        this.applyMove(move);
        this.history.push(cloneMove(move));
        this.lastMove = cloneMove(move);
        this.turn = this.opposite(this.turn);
        this.selected = null;
        this.legalTargets = [];
        this.refreshStatus();

        if (this.status.includes("Jaque mate") || this.status.includes("Tablas")) {
            this.pendingSound = "game-end";
        } else if (this.status.includes("Jaque")) {
            this.pendingSound = "move-check";
        } else if (move.promotion) {
            this.pendingSound = "promote";
        } else if (move.castle) {
            this.pendingSound = "castle";
        } else if (move.captured) {
            this.pendingSound = "capture";
        } else {
            this.pendingSound = movingColor === "w" ? "move-self" : "move-opponent";
        }
    }

    applyMove(move) {
        const [startRow, startCol] = move.start;
        const [endRow, endCol] = move.end;
        const piece = this.board[startRow][startCol];
        this.board[startRow][startCol] = null;

        if (move.enPassant) {
            this.board[startRow][endCol] = null;
        }

        if (move.castle) {
            if (endCol === 6) {
                this.board[endRow][5] = this.board[endRow][7];
                this.board[endRow][7] = null;
            } else {
                this.board[endRow][3] = this.board[endRow][0];
                this.board[endRow][0] = null;
            }
        }

        this.board[endRow][endCol] = move.promotion || piece;
        this.updateCastlingRights(move);
        this.enPassantTarget = null;
        if (piece && piece.toUpperCase() === "P" && Math.abs(endRow - startRow) === 2) {
            this.enPassantTarget = [(startRow + endRow) / 2, startCol];
        }
    }

    updateCastlingRights(move) {
        const [startRow, startCol] = move.start;
        const [endRow, endCol] = move.end;

        if (move.piece === "K") {
            this.castling.K = false;
            this.castling.Q = false;
        } else if (move.piece === "k") {
            this.castling.k = false;
            this.castling.q = false;
        } else if (move.piece === "R" && startRow === 7 && startCol === 0) {
            this.castling.Q = false;
        } else if (move.piece === "R" && startRow === 7 && startCol === 7) {
            this.castling.K = false;
        } else if (move.piece === "r" && startRow === 0 && startCol === 0) {
            this.castling.q = false;
        } else if (move.piece === "r" && startRow === 0 && startCol === 7) {
            this.castling.k = false;
        }

        if (move.captured === "R" && endRow === 7 && endCol === 0) this.castling.Q = false;
        if (move.captured === "R" && endRow === 7 && endCol === 7) this.castling.K = false;
        if (move.captured === "r" && endRow === 0 && endCol === 0) this.castling.q = false;
        if (move.captured === "r" && endRow === 0 && endCol === 7) this.castling.k = false;
    }

    refreshStatus() {
        const colorName = this.turn === "w" ? "blancas" : "negras";
        const moves = this.allLegalMoves(this.turn);
        if (this.isInCheck(this.turn) && moves.length === 0) {
            this.status = `Jaque mate: ganan ${this.turn === "w" ? "negras" : "blancas"}`;
        } else if (moves.length === 0) {
            this.status = "Tablas por ahogado";
        } else if (this.isInCheck(this.turn)) {
            this.status = `Jaque a ${colorName}`;
        } else {
            this.status = `Juegan ${colorName}`;
        }
    }

    updateClock(deltaSeconds) {
        if (this.gameOver()) return;
        const previous = this.clocks[this.turn];
        this.clocks[this.turn] = Math.max(0, this.clocks[this.turn] - deltaSeconds);
        if (this.clocks[this.turn] <= 0) {
            this.status = `Tiempo agotado: ganan ${this.turn === "w" ? "negras" : "blancas"}`;
            this.selected = null;
            this.legalTargets = [];
            this.pendingSound = "game-end";
        } else if (previous > 10 && this.clocks[this.turn] <= 10 && !this.lowTimeWarning[this.turn]) {
            this.lowTimeWarning[this.turn] = true;
            this.pendingSound = "tenseconds";
        }
    }

    clockText(color) {
        const total = Math.max(0, Math.ceil(this.clocks[color]));
        const minutes = Math.floor(total / 60);
        const seconds = total % 60;
        return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
    }

    gameOver() {
        return this.status.includes("Jaque mate") || this.status.includes("Tablas") || this.status.includes("Tiempo agotado");
    }

    moveLabel(move) {
        if (move.castle) return move.end[1] === 6 ? "O-O" : "O-O-O";
        const name = PIECE_NAMES[move.piece.toUpperCase()];
        const capture = move.captured ? "x" : "-";
        const suffix = move.promotion ? "=Q" : "";
        return `${name} ${algebraic(move.start)}${capture}${algebraic(move.end)}${suffix}`;
    }
}

const elements = {
    board: document.getElementById("board"),
    statusText: document.getElementById("statusText"),
    turnText: document.getElementById("turnText"),
    whiteClock: document.getElementById("whiteClock"),
    blackClock: document.getElementById("blackClock"),
    whiteClockText: document.getElementById("whiteClockText"),
    blackClockText: document.getElementById("blackClockText"),
    historyList: document.getElementById("historyList"),
    historyCount: document.getElementById("historyCount"),
    whiteCaptures: document.getElementById("whiteCaptures"),
    blackCaptures: document.getElementById("blackCaptures"),
    restartButton: document.getElementById("restartButton"),
    flipButton: document.getElementById("flipButton"),
};

const assets = {
    pieceImages: {},
    sounds: {},
};

const game = new ChessGame();
const squareElements = [];
let lastTick = performance.now();
let audioUnlocked = false;

function createMove(start, end, piece, captured = null, promotion = null) {
    return {
        start: [...start],
        end: [...end],
        piece,
        captured,
        promotion,
        castle: false,
        enPassant: false,
    };
}

function cloneMove(move) {
    return {
        ...move,
        start: [...move.start],
        end: [...move.end],
    };
}

function sameSquare(a, b) {
    return a && b && a[0] === b[0] && a[1] === b[1];
}

function algebraic(square) {
    const [row, col] = square;
    return `${String.fromCharCode(97 + col)}${8 - row}`;
}

function boardToView(square) {
    if (!game.flipped) return square;
    return [7 - square[0], 7 - square[1]];
}

function viewToBoard(square) {
    if (!game.flipped) return square;
    return [7 - square[0], 7 - square[1]];
}

function pieceAssetKey(piece) {
    const color = piece === piece.toUpperCase() ? "w" : "b";
    return `${color}${piece.toUpperCase()}`;
}

function preloadAssets() {
    for (const color of ["w", "b"]) {
        for (const kind of PIECE_ORDER) {
            const key = `${color}${kind}`;
            const img = new Image();
            img.src = `assets/pieces/${key}.png`;
            assets.pieceImages[key] = img;
        }
    }

    const soundMap = [
        "capture",
        "castle",
        "game-end",
        "game-start",
        "illegal",
        "move-check",
        "move-opponent",
        "move-self",
        "promote",
        "tenseconds",
    ];

    for (const soundName of soundMap) {
        assets.sounds[soundName] = new Audio(`assets/sounds/${soundName}.mp3`);
        assets.sounds[soundName].preload = "auto";
    }
}

function unlockAudio() {
    if (audioUnlocked) return;
    audioUnlocked = true;
    Object.values(assets.sounds).forEach((audio) => {
        audio.volume = 0;
        audio.play().then(() => {
            audio.pause();
            audio.currentTime = 0;
            audio.volume = 1;
        }).catch(() => {
            audio.volume = 1;
        });
    });
}

function playSound(name) {
    const audio = assets.sounds[name];
    if (!audio) return;
    try {
        audio.currentTime = 0;
        audio.play().catch(() => {});
    } catch (error) {
        console.warn("No se pudo reproducir", name, error);
    }
}

function buildBoard() {
    elements.board.innerHTML = "";
    squareElements.length = 0;

    for (let viewRow = 0; viewRow < 8; viewRow += 1) {
        for (let viewCol = 0; viewCol < 8; viewCol += 1) {
            const square = document.createElement("button");
            square.type = "button";
            square.className = `square ${(viewRow + viewCol) % 2 === 0 ? "light" : "dark"}`;
            square.dataset.viewRow = String(viewRow);
            square.dataset.viewCol = String(viewCol);
            square.addEventListener("click", () => {
                unlockAudio();
                onSquareClick([viewRow, viewCol]);
            });
            elements.board.appendChild(square);
            squareElements.push(square);
        }
    }
}

function onSquareClick(viewSquare) {
    const boardSquare = viewToBoard(viewSquare);
    const move = game.handleSquareClick(boardSquare);
    if (move) {
        animateMove(move);
    }
    flushPendingSound();
    render();
}

function animateMove(move) {
    const startView = boardToView(move.start);
    const endView = boardToView(move.end);
    const startSquare = getSquareElement(startView);
    const endSquare = getSquareElement(endView);
    const startImg = startSquare.querySelector("img");
    if (!startImg) {
        game.hiddenSquare = null;
        return;
    }

    const floating = startImg.cloneNode(true);
    floating.className = "moving-piece";
    document.body.appendChild(floating);

    const startBox = startSquare.getBoundingClientRect();
    const endBox = endSquare.getBoundingClientRect();
    floating.style.left = `${startBox.left}px`;
    floating.style.top = `${startBox.top}px`;
    floating.style.width = `${startBox.width}px`;
    floating.style.height = `${startBox.height}px`;

    floating.animate(
        [
            { transform: "translate(0, 0) scale(1)", opacity: 1 },
            { transform: `translate(${endBox.left - startBox.left}px, ${endBox.top - startBox.top}px) scale(1.02)`, opacity: 1 },
        ],
        {
            duration: 180,
            easing: "cubic-bezier(0.2, 0.8, 0.2, 1)",
        },
    ).finished.finally(() => {
        floating.remove();
        game.hiddenSquare = null;
        render();
    });
}

function flushPendingSound() {
    if (!game.pendingSound) return;
    playSound(game.pendingSound);
    game.pendingSound = null;
}

function getSquareElement(viewSquare) {
    const [viewRow, viewCol] = viewSquare;
    return squareElements[viewRow * 8 + viewCol];
}

function render() {
    renderBoard();
    renderSidebar();
}

function renderBoard() {
    const checkedKing = game.isInCheck(game.turn) ? game.kingSquare(game.turn) : null;
    const legalEnds = new Map(game.legalTargets.map((move) => [move.end.join(","), move]));

    squareElements.forEach((squareElement) => {
        const viewRow = Number(squareElement.dataset.viewRow);
        const viewCol = Number(squareElement.dataset.viewCol);
        const boardSquare = viewToBoard([viewRow, viewCol]);
        const [boardRow, boardCol] = boardSquare;
        const piece = game.board[boardRow][boardCol];
        const move = legalEnds.get(boardSquare.join(","));

        squareElement.classList.toggle("selected", sameSquare(game.selected, boardSquare));
        squareElement.classList.toggle("last", Boolean(game.lastMove && (sameSquare(game.lastMove.start, boardSquare) || sameSquare(game.lastMove.end, boardSquare))));
        squareElement.classList.toggle("in-check", Boolean(checkedKing && sameSquare(checkedKing, boardSquare)));
        squareElement.classList.toggle("target", Boolean(move && !move.captured));
        squareElement.classList.toggle("capture-target", Boolean(move && move.captured));

        squareElement.innerHTML = "";

        const showRank = viewCol === 0;
        const showFile = viewRow === 7;
        if (showRank) {
            const rank = document.createElement("span");
            rank.className = "square-label rank";
            rank.textContent = String(8 - boardSquare[0]);
            squareElement.appendChild(rank);
        }
        if (showFile) {
            const file = document.createElement("span");
            file.className = "square-label file";
            file.textContent = String.fromCharCode(97 + boardSquare[1]);
            squareElement.appendChild(file);
        }

        if (piece && !(game.hiddenSquare && sameSquare(game.hiddenSquare, boardSquare))) {
            const pieceWrap = document.createElement("div");
            pieceWrap.className = "piece";
            const img = document.createElement("img");
            img.src = assets.pieceImages[pieceAssetKey(piece)].src;
            img.alt = PIECE_NAMES[piece.toUpperCase()];
            pieceWrap.appendChild(img);
            squareElement.appendChild(pieceWrap);
        }
    });
}

function renderSidebar() {
    elements.statusText.textContent = game.status;
    elements.turnText.textContent = game.gameOver()
        ? "La partida termino"
        : `Turno actual: ${game.turn === "w" ? "blancas" : "negras"}`;

    elements.whiteClockText.textContent = game.clockText("w");
    elements.blackClockText.textContent = game.clockText("b");
    elements.whiteClock.classList.toggle("active", game.turn === "w" && !game.gameOver());
    elements.blackClock.classList.toggle("active", game.turn === "b" && !game.gameOver());
    elements.whiteClock.classList.toggle("low", game.clocks.w <= 10);
    elements.blackClock.classList.toggle("low", game.clocks.b <= 10);

    elements.historyCount.textContent = `${game.history.length} movimiento${game.history.length === 1 ? "" : "s"}`;
    elements.historyList.innerHTML = "";
    if (game.history.length === 0) {
        const empty = document.createElement("p");
        empty.className = "muted";
        empty.textContent = "Todavia no se ha jugado ninguna pieza.";
        elements.historyList.appendChild(empty);
    } else {
        game.history.slice().reverse().forEach((move, index) => {
            const row = document.createElement("div");
            row.className = "history-item";
            const label = document.createElement("span");
            label.textContent = game.moveLabel(move);
            const number = document.createElement("strong");
            number.textContent = `#${game.history.length - index}`;
            row.append(number, label);
            elements.historyList.appendChild(row);
        });
    }

    const captures = collectCaptures();
    renderCaptureRow(elements.whiteCaptures, captures.white);
    renderCaptureRow(elements.blackCaptures, captures.black);
}

function collectCaptures() {
    const result = { white: [], black: [] };
    for (const move of game.history) {
        if (!move.captured) continue;
        if (move.captured === move.captured.toUpperCase()) {
            result.black.push(move.captured);
        } else {
            result.white.push(move.captured);
        }
    }
    return result;
}

function renderCaptureRow(container, pieces) {
    container.innerHTML = "";
    pieces.forEach((piece) => {
        const chip = document.createElement("div");
        chip.className = "capture-chip";
        const img = document.createElement("img");
        img.src = assets.pieceImages[pieceAssetKey(piece)].src;
        img.alt = PIECE_NAMES[piece.toUpperCase()];
        chip.appendChild(img);
        container.appendChild(chip);
    });
}

function tick(now) {
    const delta = Math.min((now - lastTick) / 1000, 0.25);
    lastTick = now;
    game.updateClock(delta);
    flushPendingSound();
    renderSidebar();
    requestAnimationFrame(tick);
}

function wireControls() {
    elements.restartButton.addEventListener("click", () => {
        unlockAudio();
        game.reset();
        render();
        flushPendingSound();
    });

    elements.flipButton.addEventListener("click", () => {
        game.flipped = !game.flipped;
        renderBoard();
    });

    window.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            game.selected = null;
            game.legalTargets = [];
            renderBoard();
        } else if (event.key.toLowerCase() === "r") {
            unlockAudio();
            game.reset();
            render();
            flushPendingSound();
        } else if (event.key.toLowerCase() === "f") {
            game.flipped = !game.flipped;
            renderBoard();
        }
    });
}

function init() {
    preloadAssets();
    buildBoard();
    wireControls();
    render();
    requestAnimationFrame((now) => {
        lastTick = now;
        requestAnimationFrame(tick);
    });
}

init();
