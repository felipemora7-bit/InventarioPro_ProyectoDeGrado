import csv
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import datetime

# CONFIGURACIÓN GENERAL
DB = Path(__file__).resolve().with_name("inventariopro.db")

C = {
    "bg": "#F3F6FB",
    "white": "#FFFFFF",
    "nav": "#172554",
    "blue": "#4169E1",
    "text": "#182230",
    "muted": "#667085",
    "border": "#E4EAF2",
    "green": "#14804A",
    "red": "#C43232",
    "orange": "#A65D03"
}


# BASE DE DATOS SQLITE
class StockDB:

    def __init__(self):
        self.con = sqlite3.connect(DB)
        self.con.row_factory = sqlite3.Row

        with self.con:
            self.con.executescript("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY,
                    code TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    category TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    price REAL NOT NULL CHECK(price >= 0),
                    qty INTEGER NOT NULL CHECK(qty >= 0),
                    minimum INTEGER NOT NULL CHECK(minimum >= 0)
                );

                CREATE TABLE IF NOT EXISTS movements (
                    id INTEGER PRIMARY KEY,
                    product_id INTEGER NOT NULL,
                    code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    qty INTEGER NOT NULL CHECK(qty > 0),
                    note TEXT DEFAULT '',
                    date TEXT NOT NULL,
                    FOREIGN KEY(product_id)
                        REFERENCES products(id)
                );
            """)

    def all(self, search=""):
        s = f"%{search.strip()}%"

        return self.con.execute("""
            SELECT * FROM products
            WHERE code LIKE ?
               OR name LIKE ?
               OR category LIKE ?
            ORDER BY name
        """, (s, s, s)).fetchall()

    def get(self, pid):
        return self.con.execute(
            "SELECT * FROM products WHERE id=?", (pid,)
        ).fetchone()

    def save(self, data, pid=None):
        code, name, cat, desc, price, qty, minimum = data

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.con:

            if pid:
                old = self.get(pid)

                self.con.execute("""
                    UPDATE products
                    SET code=?, name=?, category=?, description=?,
                        price=?, qty=?, minimum=?
                    WHERE id=?
                """, (*data, pid))

                delta = qty - old["qty"]

                if delta:
                    self.con.execute("""
                        INSERT INTO movements
                        (product_id, code, name, kind, qty, note, date)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        pid, code, name,
                        "Entrada" if delta > 0 else "Salida",
                        abs(delta),
                        "Ajuste al editar producto",
                        now
                    ))

            else:
                cur = self.con.execute("""
                    INSERT INTO products
                    (code, name, category, description,
                     price, qty, minimum)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, data)

                pid = cur.lastrowid

                if qty:
                    self.con.execute("""
                        INSERT INTO movements
                        (product_id, code, name, kind,
                         qty, note, date)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        pid, code, name, "Entrada", qty,
                        "Existencia inicial", now
                    ))

        return pid

    def delete(self, pid):
        with self.con:
            self.con.execute(
                "DELETE FROM movements WHERE product_id=?", (pid,)
            )
            self.con.execute(
                "DELETE FROM products WHERE id=?", (pid,)
            )

    def move(self, pid, kind, qty, note):
        p = self.get(pid)

        if not p:
            raise ValueError("Selecciona un producto...")

        if qty <= 0:
            raise ValueError("La cantidad debe ser mayor que cero...")

        if kind == "Entrada":
            new = p["qty"] + qty
        else:
            new = p["qty"] - qty

        if new < 0:
            raise ValueError(
                f"Existencias insuficientes. Disponible: {p['qty']}."
            )

        with self.con:
            self.con.execute(
                "UPDATE products SET qty=? WHERE id=?",
                (new, pid)
            )

            self.con.execute("""
                INSERT INTO movements
                (product_id, code, name, kind, qty, note, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                pid, p["code"], p["name"], kind, qty, note,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

    def history(self, search=""):
        s = f"%{search.strip()}%"

        return self.con.execute("""
            SELECT * FROM movements
            WHERE name LIKE ?
               OR code LIKE ?
               OR kind LIKE ?
            ORDER BY id DESC
        """, (s, s, s)).fetchall()

    def stats(self):
        return self.con.execute("""
            SELECT
                COUNT(*) AS products,
                COALESCE(SUM(qty), 0) AS units,
                COALESCE(SUM(qty * price), 0) AS value,
                COALESCE(SUM(qty <= minimum), 0) AS low
            FROM products
        """).fetchone()

    def close(self):
        self.con.close()


# APLICACIÓN PRINCIPAL
class App(tk.Tk):

    def __init__(self):
        super().__init__()

        self.db = StockDB()

        self.title("InventPro | Gestión de inventario")
        self.geometry("1160x720")
        self.minsize(960, 600)
        self.configure(bg=C["bg"])

        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(
            "Treeview",
            rowheight=29,
            font=("Segoe UI", 10),
            background="white",
            fieldbackground="white",
            foreground=C["text"]
        )

        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background="#EAF0F8",
            foreground=C["text"],
            padding=8
        )

        style.map(
            "Treeview",
            background=[("selected", "#DCE7FF")]
        )

        self.make_layout()
        self.show("Inicio")

        self.protocol("WM_DELETE_WINDOW", self.close)

    def button(self, parent, text, cmd, color=None):
        return tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=color or C["blue"],
            fg="white",
            activebackground="#3155C7",
            activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            bd=0,
            padx=13,
            pady=8,
            cursor="hand2"
        )


    # INTERFAZ Y NAVEGACIÓN
    def make_layout(self):
        side = tk.Frame(self, bg=C["nav"], width=220)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        tk.Label(
            side,
            text="▦  InventPro",
            bg=C["nav"],
            fg="white",
            font=("Segoe UI", 20, "bold")
        ).pack(anchor="w", padx=20, pady=(28, 3))

        tk.Label(
            side,
            text="INVENTARIO INTELIGENTE",
            bg=C["nav"],
            fg="#AAB8D5",
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", padx=22, pady=(0, 30))

        self.nav = {}

        items = [
            ("⌂", "Inicio"),
            ("▤", "Inventario"),
            ("↓", "Entradas"),
            ("↑", "Salidas"),
            ("⚑", "Existencias bajas"),
            ("◷", "Historial")
        ]

        for icon, name in items:
            b = tk.Button(
                side,
                text=f"  {icon}    {name}",
                anchor="w",
                command=lambda n=name: self.show(n),
                bg=C["nav"],
                fg="#D9E2F4",
                activebackground="#243B73",
                activeforeground="white",
                font=("Segoe UI", 10, "bold"),
                bd=0,
                padx=15,
                pady=11,
                cursor="hand2"
            )

            b.pack(fill="x", padx=10, pady=2)
            self.nav[name] = b

        # Salida segura desde el menú lateral.
        exit_button = tk.Button(
            side,
            text="  ⏻    Salir",
            anchor="w",
            command=self.confirm_exit,
            bg=C["nav"],
            fg="#FCA5A5",
            activebackground="#243B73",
            activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            bd=0,
            padx=15,
            pady=11,
            cursor="hand2"
        )
        exit_button.pack(fill="x", padx=10, pady=(2, 8))

        tk.Frame(
            side, bg="#34466D", height=1
        ).pack(fill="x", padx=18, pady=(18, 12))

        tk.Label(
            side,
            text="PROTOTIPO FUNCIONAL",
            bg=C["nav"],
            fg="#AAB8D5",
            font=("Segoe UI", 8, "bold")
        ).pack(anchor="w", padx=20)

        tk.Label(
            side,
            text="Python • SQLite",
            bg=C["nav"],
            fg="#AAB8D5",
            font=("Segoe UI", 9)
        ).pack(anchor="w", padx=20, pady=(5, 3))

        tk.Label(
            side,
            text="Felipe Mora - 84 :)",
            bg=C["nav"],
            fg="#AAB8D5",
            font=("Segoe UI", 9)
        ).pack(anchor="w", padx=20, pady=(0, 8))

        main = tk.Frame(self, bg=C["bg"])
        main.pack(side="left", fill="both", expand=True)

        head = tk.Frame(
            main,
            bg="white",
            height=75,
            highlightbackground=C["border"],
            highlightthickness=1
        )

        head.pack(fill="x")
        head.pack_propagate(False)

        self.titlelabel = tk.Label(
            head,
            text="",
            bg="white",
            fg=C["text"],
            font=("Segoe UI", 20, "bold")
        )

        self.titlelabel.pack(side="left", padx=27)

        tk.Label(
            head,
            text="●  Sistema local activo",
            bg="white",
            fg=C["green"],
            font=("Segoe UI", 10)
        ).pack(side="right", padx=25)

        self.body = tk.Frame(main, bg=C["bg"])
        self.body.pack(
            fill="both",
            expand=True,
            padx=22,
            pady=20
        )

    def show(self, page):
        self.page = page
        self.titlelabel.config(text=page)

        for name, button in self.nav.items():
            button.config(
                bg=C["blue"] if name == page else C["nav"],
                fg="white" if name == page else "#D9E2F4"
            )

        for widget in self.body.winfo_children():
            widget.destroy()

        pages = {
            "Inicio": self.home,
            "Inventario": self.inventory,
            "Entradas": lambda: self.movement("Entrada"),
            "Salidas": lambda: self.movement("Salida"),
            "Existencias bajas": self.low,
            "Historial": self.history
        }

        pages[page]()

    def label(self, parent, text, size=10, bold=False,
              color=None, bg=None):
        return tk.Label(
            parent,
            text=text,
            font=("Segoe UI", size, "bold" if bold else "normal"),
            fg=color or C["text"],
            bg=bg or C["bg"]
        )

    def table(self, parent, cols, heads, widths=None):
        box = tk.Frame(
            parent,
            bg="white",
            highlightbackground=C["border"],
            highlightthickness=1
        )

        box.pack(fill="both", expand=True)

        tree = ttk.Treeview(
            box,
            columns=cols,
            show="headings"
        )

        for i, col in enumerate(cols):
            tree.heading(col, text=heads[i])
            tree.column(
                col,
                width=widths[i] if widths else 120,
                anchor="w"
            )

        scroll = ttk.Scrollbar(
            box,
            orient="vertical",
            command=tree.yview
        )

        tree.configure(yscrollcommand=scroll.set)

        tree.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(7, 0),
            pady=7
        )

        scroll.pack(
            side="right",
            fill="y",
            padx=(0, 5),
            pady=7
        )

        return tree


    # PANTALLA DE INICIO
    def home(self):
        s = self.db.stats()

        moves = self.db.con.execute(
            "SELECT COUNT(*) FROM movements"
        ).fetchone()[0]

        self.label(
            self.body,
            "Tu inventario, de un vistazo",
            15,
            True
        ).pack(anchor="w")

        self.label(
            self.body,
            "Administra productos, movimientos y existencias desde un solo lugar :)",
            10,
            color=C["muted"]
        ).pack(anchor="w", pady=(4, 18))

        cards = tk.Frame(self.body, bg=C["bg"])
        cards.pack(fill="x", pady=(0, 25))

        data = [
            ("PRODUCTOS", s["products"], "Referencias registradas", C["blue"], "▤"),
            ("UNIDADES", s["units"], "Unidades disponibles", C["green"], "▦"),
            ("STOCK BAJO", s["low"], "Necesitan revisión", C["red"], "⚑"),
            ("MOVIMIENTOS", moves, "Entradas y salidas", "#7857C5", "◷")
        ]

        for title, val, sub, col, icon in data:
            f = tk.Frame(
                cards,
                bg="white",
                highlightbackground=C["border"],
                highlightthickness=1
            )

            f.pack(
                side="left",
                fill="both",
                expand=True,
                padx=(0, 12)
            )

            tk.Label(
                f,
                text=icon,
                bg=col,
                fg="white",
                font=("Segoe UI", 14, "bold"),
                padx=10,
                pady=5
            ).pack(anchor="ne", padx=13, pady=(13, 0))

            self.label(
                f, title, 9, True, C["muted"], "white"
            ).pack(anchor="w", padx=16)

            self.label(
                f, str(val), 24, True, bg="white"
            ).pack(anchor="w", padx=16)

            self.label(
                f, sub, 9, color=C["muted"], bg="white"
            ).pack(anchor="w", padx=16, pady=(0, 15))

        self.label(
            self.body, "Accesos rápidos", 13, True
        ).pack(anchor="w", pady=(0, 10))

        row = tk.Frame(self.body, bg=C["bg"])
        row.pack(anchor="w", pady=(0, 24))

        self.button(
            row, "＋ Nuevo producto", self.product_form
        ).pack(side="left", padx=(0, 9))

        self.button(
            row, "↓ Registrar entrada",
            lambda: self.show("Entradas"), C["green"]
        ).pack(side="left", padx=(0, 9))

        self.button(
            row, "↑ Registrar salida",
            lambda: self.show("Salidas"), "#B54708"
        ).pack(side="left", padx=(0, 9))

        self.button(
            row, "▤ Ver inventario",
            lambda: self.show("Inventario"), C["nav"]
        ).pack(side="left")

        self.label(
            self.body, "Productos que requieren atención", 13, True
        ).pack(anchor="w", pady=(0, 10))

        rows = self.db.con.execute("""
            SELECT * FROM products
            WHERE qty <= minimum
            ORDER BY qty, name
        """).fetchall()

        if rows:
            t = self.table(
                self.body,
                ("code", "name", "qty", "minimum"),
                ("CÓDIGO", "PRODUCTO", "EXISTENCIAS", "MÍNIMO"),
                (140, 350, 150, 130)
            )

            for r in rows[:7]:
                t.insert(
                    "", "end",
                    values=(r["code"], r["name"], r["qty"], r["minimum"])
                )

        else:
            self.label(
                self.body,
                "✓  No hay productos con existencias bajas.",
                11,
                True,
                C["green"],
                "white"
            ).pack(fill="x", pady=10, ipady=20)


    # INVENTARIO: CONSULTAR, BUSCAR, EDITAR Y ELIMINAR
    def inventory(self):
        bar = tk.Frame(self.body, bg=C["bg"])
        bar.pack(fill="x", pady=(0, 13))

        search = tk.StringVar()

        ttk.Entry(
            bar, textvariable=search, width=33
        ).pack(side="left", ipady=7)

        self.label(
            bar, "Busca por código, nombre o categoría",
            9, color=C["muted"]
        ).pack(side="left", padx=10)

        self.button(
            bar, "＋ Nuevo producto", self.product_form
        ).pack(side="right", padx=(8, 0))

        self.button(
            bar, "⇩ Exportar CSV", self.export, C["green"]
        ).pack(side="right")

        t = self.table(
            self.body,
            ("id", "code", "name", "category", "price",
             "qty", "minimum", "total"),
            ("ID", "CÓDIGO", "PRODUCTO", "CATEGORÍA",
             "PRECIO", "CANTIDAD", "MÍNIMO", "VALOR TOTAL"),
            (45, 95, 190, 120, 100, 85, 80, 120)
        )

        t.column("id", width=0, stretch=False)

        def refresh(*_):
            t.delete(*t.get_children())

            for p in self.db.all(search.get()):
                t.insert(
                    "",
                    "end",
                    iid=str(p["id"]),
                    values=(
                        p["id"], p["code"], p["name"],
                        p["category"], f"${p['price']:,.2f}",
                        p["qty"], p["minimum"],
                        f"${p['price'] * p['qty']:,.2f}"
                    )
                )

        search.trace_add("write", refresh)
        refresh()

        row = tk.Frame(self.body, bg=C["bg"])
        row.pack(fill="x", pady=12)

        def selected():
            sel = t.selection()

            if not sel:
                messagebox.showinfo(
                    "Selecciona un producto",
                    "Primero selecciona una fila de la tabla."
                )
                return None

            return int(sel[0])

        def edit():
            pid = selected()
            if pid is not None:
                self.product_form(pid)

        self.button(
            row, "✎ Editar seleccionado",
            edit, C["nav"]
        ).pack(side="left", padx=(0, 8))

        def delete():
            pid = selected()

            if pid is not None and messagebox.askyesno(
                "Confirmar",
                "¿Eliminar el producto y sus movimientos? "
                "Esta acción no se puede deshacer."
            ):
                self.db.delete(pid)
                self.show("Inventario")

        self.button(
            row, "⌫ Eliminar seleccionado",
            delete, C["red"]
        ).pack(side="left")

        t.bind(
            "<Double-1>",
            lambda e: self.product_form(int(t.selection()[0]))
            if t.selection() else None
        )


    # FORMULARIO PARA REGISTRAR O EDITAR PRODUCTOS
    def product_form(self, pid=None):
        p = self.db.get(pid) if pid else None

        w = tk.Toplevel(self)
        w.title("Editar producto" if p else "Nuevo producto")
        w.configure(bg=C["bg"])
        w.geometry("500x545")
        w.resizable(False, False)
        w.transient(self)
        w.grab_set()

        self.label(
            w,
            "Editar producto" if p else "Registrar producto",
            17,
            True
        ).pack(anchor="w", padx=22, pady=(18, 3))

        self.label(
            w, "Completa los datos del artículo.",
            9, color=C["muted"]
        ).pack(anchor="w", padx=25, pady=(0, 14))

        form = tk.Frame(
            w,
            bg="white",
            highlightbackground=C["border"],
            highlightthickness=1
        )

        form.pack(fill="both", expand=True, padx=20, pady=(0, 13))

        fields = [
            ("Código *", "code", p["code"] if p else ""),
            ("Nombre *", "name", p["name"] if p else ""),
            ("Categoría", "category", p["category"] if p else ""),
            ("Descripción", "description", p["description"] if p else ""),
            ("Precio unitario *", "price", str(p["price"]) if p else "0"),
            ("Cantidad inicial *", "qty", str(p["qty"] if p else 0)),
            ("Mínimo para alerta *", "minimum", str(p["minimum"] if p else 5))
        ]

        vars = {}

        for lab, key, val in fields:
            r = tk.Frame(form, bg="white")
            r.pack(fill="x", padx=15, pady=4)

            tk.Label(
                r,
                text=lab,
                bg="white",
                fg=C["text"],
                font=("Segoe UI", 9, "bold"),
                width=18,
                anchor="w"
            ).pack(side="left")

            v = tk.StringVar(value=val)

            ttk.Entry(
                r, textvariable=v, width=30
            ).pack(side="left", fill="x", expand=True, ipady=5)

            vars[key] = v

        def save():
            code = vars["code"].get().strip()
            name = vars["name"].get().strip()

            if not code or not name:
                messagebox.showwarning(
                    "Faltan datos",
                    "Código y nombre son obligatorios.",
                    parent=w
                )
                return

            try:
                price = float(vars["price"].get().replace(",", "."))
                qty = int(vars["qty"].get())
                minimum = int(vars["minimum"].get())

                if price < 0 or qty < 0 or minimum < 0:
                    raise ValueError

            except ValueError:
                messagebox.showwarning(
                    "Datos inválidos",
                    "El precio debe ser cero o positivo; "
                    "cantidad y mínimo deben ser enteros no negativos.",
                    parent=w
                )
                return

            data = (
                code,
                name,
                vars["category"].get().strip(),
                vars["description"].get().strip(),
                price,
                qty,
                minimum
            )

            try:
                self.db.save(data, pid)

            except sqlite3.IntegrityError:
                messagebox.showerror(
                    "Código duplicado",
                    "Ya existe un producto con ese código.",
                    parent=w
                )
                return

            w.destroy()

            self.show(
                "Inventario" if self.page != "Inicio" else "Inicio"
            )

        buttons = tk.Frame(w, bg=C["bg"])
        buttons.pack(fill="x", padx=20, pady=(0, 15))

        self.button(
            buttons, "Cancelar", w.destroy, "#667085"
        ).pack(side="right", padx=(8, 0))

        self.button(
            buttons, "Guardar producto", save, C["blue"]
        ).pack(side="right")


    # REGISTRO DE ENTRADAS Y SALIDAS
    def movement(self, kind):
        is_in = kind == "Entrada"
        color = C["green"] if is_in else "#B54708"

        self.label(
            self.body,
            "Registrar " + ("entrada" if is_in else "salida")
            + " de mercancía",
            16,
            True
        ).pack(anchor="w")

        self.label(
            self.body,
            "El inventario se actualizará y el movimiento "
            "quedará guardado automáticamente.",
            10,
            color=C["muted"]
        ).pack(anchor="w", pady=(5, 20))

        form = tk.Frame(
            self.body,
            bg="white",
            highlightbackground=C["border"],
            highlightthickness=1
        )

        form.pack(fill="x")

        inner = tk.Frame(form, bg="white")
        inner.pack(fill="x", padx=28, pady=25)

        products = self.db.all()

        choices = [
            f"{p['code']} — {p['name']} "
            f"(disponible: {p['qty']})"
            for p in products
        ]

        pv = tk.StringVar(value=choices[0] if choices else "")
        qv = tk.StringVar(value="1")
        nv = tk.StringVar()

        tk.Label(
            inner, text="Producto *",
            bg="white", font=("Segoe UI", 10, "bold")
        ).pack(anchor="w")

        ttk.Combobox(
            inner,
            textvariable=pv,
            values=choices,
            state="readonly",
            width=65
        ).pack(anchor="w", pady=(5, 16), ipady=5)

        tk.Label(
            inner, text="Cantidad *",
            bg="white", font=("Segoe UI", 10, "bold")
        ).pack(anchor="w")

        ttk.Entry(
            inner, textvariable=qv, width=20
        ).pack(anchor="w", pady=(5, 16), ipady=5)

        tk.Label(
            inner, text="Nota o motivo (opcional)",
            bg="white", font=("Segoe UI", 10, "bold")
        ).pack(anchor="w")

        ttk.Entry(
            inner, textvariable=nv, width=65
        ).pack(anchor="w", pady=(5, 20), ipady=5)

        def submit():
            if not products or not pv.get():
                messagebox.showwarning(
                    "Sin productos",
                    "Registra primero un producto en Inventario."
                )
                return

            try:
                qty = int(qv.get())

                if qty <= 0:
                    raise ValueError

            except ValueError:
                messagebox.showwarning(
                    "Cantidad inválida",
                    "Escribe un entero mayor que cero."
                )
                return

            code = pv.get().split(" — ")[0]

            p = next(
                p for p in products if p["code"] == code
            )

            try:
                self.db.move(
                    p["id"], kind, qty, nv.get().strip()
                )

            except ValueError as e:
                messagebox.showerror(
                    "No se pudo registrar", str(e)
                )
                return

            messagebox.showinfo(
                "Correcto",
                f"{kind} registrada correctamente."
            )

            self.show("Entradas" if is_in else "Salidas")

        self.button(
            inner,
            "↓  Confirmar entrada" if is_in
            else "↑  Confirmar salida",
            submit,
            color
        ).pack(anchor="w")

        if not products:
            self.label(
                self.body,
                "Primero ve a Inventario y registra un producto.",
                10,
                True,
                C["orange"]
            ).pack(anchor="w", pady=15)

           
    # ALERTAS DE EXISTENCIAS BAJAS
    def low(self):
        self.label(
            self.body, "Control de reposición", 14, True
        ).pack(anchor="w")

        self.label(
            self.body,
            "Productos con cantidad igual o inferior al mínimo configurado.",
            10,
            color=C["muted"]
        ).pack(anchor="w", pady=(4, 14))

        rows = self.db.con.execute("""
            SELECT * FROM products
            WHERE qty <= minimum
            ORDER BY qty, name
        """).fetchall()

        if not rows:
            self.label(
                self.body,
                "✓  No hay productos con existencias bajas.",
                11,
                True,
                C["green"],
                "white"
            ).pack(fill="x", pady=10, ipady=20)
            return

        t = self.table(
            self.body,
            ("code", "name", "category", "qty", "minimum", "missing"),
            ("CÓDIGO", "PRODUCTO", "CATEGORÍA",
             "EXISTENCIAS", "MÍNIMO",
             "UNIDADES PARA LLEGAR AL MÍNIMO"),
            (120, 240, 150, 120, 100, 220)
        )

        for p in rows:
            t.insert(
                "",
                "end",
                values=(
                    p["code"],
                    p["name"],
                    p["category"],
                    p["qty"],
                    p["minimum"],
                    max(0, p["minimum"] - p["qty"])
                )
            )

   
    # HISTORIAL DE MOVIMIENTOS
    def history(self):
        bar = tk.Frame(self.body, bg=C["bg"])
        bar.pack(fill="x", pady=(0, 13))

        search = tk.StringVar()

        ttk.Entry(
            bar, textvariable=search, width=34
        ).pack(side="left", ipady=7)

        self.label(
            bar,
            "Busca por producto, código o movimiento",
            9,
            color=C["muted"]
        ).pack(side="left", padx=10)

        t = self.table(
            self.body,
            ("date", "kind", "code", "name", "qty", "note"),
            ("FECHA", "TIPO", "CÓDIGO",
             "PRODUCTO", "CANTIDAD", "NOTA / MOTIVO"),
            (165, 100, 110, 210, 90, 280)
        )

        def refresh(*_):
            t.delete(*t.get_children())

            for m in self.db.history(search.get()):
                t.insert(
                    "",
                    "end",
                    values=(
                        m["date"],
                        m["kind"],
                        m["code"],
                        m["name"],
                        m["qty"],
                        m["note"] or "—"
                    )
                )

        search.trace_add("write", refresh)
        refresh()


    # EXPORTAR INVENTARIO A CSV
    def export(self):
        rows = self.db.all()

        if not rows:
            messagebox.showinfo(
                "Sin datos", "No hay productos para exportar."
            )
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("Archivo CSV", "*.csv")],
            initialfile="inventario_inventariopro.csv"
        )

        if not path:
            return

        try:
            with open(
                path, "w", newline="", encoding="utf-8-sig"
            ) as f:

                writer = csv.writer(f, delimiter=";")

                writer.writerow([
                    "Código", "Nombre", "Categoría",
                    "Descripción", "Precio", "Cantidad",
                    "Mínimo", "Valor total"
                ])

                for p in rows:
                    writer.writerow([
                        p["code"],
                        p["name"],
                        p["category"],
                        p["description"],
                        p["price"],
                        p["qty"],
                        p["minimum"],
                        p["price"] * p["qty"]
                    ])

            messagebox.showinfo(
                "Exportado",
                "Inventario exportado correctamente."
            )

        except OSError as e:
            messagebox.showerror("Error", str(e))


    # CIERRE SEGURO
    def confirm_exit(self):
        if messagebox.askyesno(
            "Salir de InventarioPro",
            "¿Realmente quieres salir de InventarioPro?",
            parent=self
        ):
            self.db.close()
            self.destroy()

    def close(self):
        self.confirm_exit()



# INICIAR APLICACIÓN
if __name__ == "__main__":
    App().mainloop()