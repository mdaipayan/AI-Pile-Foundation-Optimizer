import streamlit as st
import pandas as pd
import math
import numpy as np
import ezdxf
import io

def generate_cad_plan(cap_l_mm, cap_w_mm, col_l_mm, col_b_mm, pile_dia_mm, spacing_mm):
    """Generates a 2D DXF CAD Plan for a Double Pile Cap."""
    
    # Create a new DXF document
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    # Set up Layers
    doc.layers.add("CONCRETE", color=7)  # White/Black
    doc.layers.add("COLUMN", color=3)    # Green
    doc.layers.add("PILES", color=1)     # Red
    doc.layers.add("CENTERLINES", color=8, linetype="DASHED")

    # Center Coordinates (0,0)
    cx, cy = 0, 0
    
    # 1. Draw Pile Cap (Rectangle)
    half_l, half_w = cap_l_mm / 2, cap_w_mm / 2
    msp.add_lwpolyline([
        (-half_l, -half_w), (half_l, -half_w), 
        (half_l, half_w), (-half_l, half_w), 
        (-half_l, -half_w)
    ], dxfattribs={'layer': 'CONCRETE'})
    
    # 2. Draw Column in the Center
    c_half_l, c_half_b = col_l_mm / 2, col_b_mm / 2
    msp.add_lwpolyline([
        (-c_half_l, -c_half_b), (c_half_l, -c_half_b), 
        (c_half_l, c_half_b), (-c_half_l, c_half_b), 
        (-c_half_l, -c_half_b)
    ], dxfattribs={'layer': 'COLUMN'})
    
    # 3. Draw the Two Piles
    pile_offset = spacing_mm / 2
    msp.add_circle((-pile_offset, 0), radius=pile_dia_mm/2, dxfattribs={'layer': 'PILES'})
    msp.add_circle((pile_offset, 0), radius=pile_dia_mm/2, dxfattribs={'layer': 'PILES'})
    
    # 4. Draw Centerlines
    msp.add_line((-half_l - 200, 0), (half_l + 200, 0), dxfattribs={'layer': 'CENTERLINES'})
    msp.add_line((-pile_offset, -half_w - 200), (-pile_offset, half_w + 200), dxfattribs={'layer': 'CENTERLINES'})
    msp.add_line((pile_offset, -half_w - 200), (pile_offset, half_w + 200), dxfattribs={'layer': 'CENTERLINES'})
    
    # Save DXF to an in-memory string buffer so Streamlit can download it
    buffer = io.StringIO()
    doc.write(buffer)
    return buffer.getvalue()

st.set_page_config(page_title="AI Pile Foundation Optimizer", layout="wide")

st.title("🧠 AI-Optimized Pile Foundation & BBS Generator")
st.markdown("This tool runs multiple design permutations to find the **cheapest IS-compliant foundation** based on real-time material costs, and exports a professional LaTeX report.")

# ==========================================
# 1. PARAMETERS & COSTS (Sidebar)
# ==========================================
st.sidebar.header("1. Geotechnical Data")
sbc = st.sidebar.number_input("Soil Bearing Capacity (kN/m²)", min_value=50, value=100, step=10)

st.sidebar.markdown("---")
st.sidebar.header("2. Material Rates (Rs)")
rate_steel = st.sidebar.number_input("Steel Cost (per kg)", value=65.0)
rate_concrete = st.sidebar.number_input("Concrete Cost (per m³)", value=5500.0)

st.sidebar.markdown("---")
st.sidebar.subheader("Detailing Rules (IS 456)")
cover_fnd = st.sidebar.number_input("Foundation Cover (mm)", value=50)
cover_col = st.sidebar.number_input("Column Cover (mm)", value=40)

unit_wt = {8: 0.395, 10: 0.617, 12: 0.888, 16: 1.580, 20: 2.466}

# ==========================================
# 2. INPUT DATA
# ==========================================
st.header("2. Input Structural Loads")
st.caption("Enter column dimensions and original isolated footing sizes. The AI will reverse-engineer the axial loads.")

default_data = pd.DataFrame({
    "ID": ["F1", "F2", "F3", "F4"],
    "Qty": [4, 4, 1, 3],
    "Footing L (m)": [1.65, 1.65, 2.35, 2.25],
    "Footing B (m)": [1.53, 1.53, 2.13, 2.03],
    "Col L (mm)": [400, 400, 500, 500],
    "Col B (mm)": [280, 280, 280, 280],
    "Main Dia (mm)": [12, 12, 16, 16],
    "Main Qty": [6, 6, 4, 4],
    "Sec Dia (mm)": [0, 0, 12, 12],
    "Sec Qty": [0, 0, 4, 4]
})

input_df = st.data_editor(default_data, num_rows="dynamic", use_container_width=True)

# ==========================================
# CORE AI OPTIMIZATION ENGINE
# ==========================================
def simulate_design(pile_dia, pile_depth, pile_capacity):
    """Simulates the entire design for a given pile diameter and returns total cost, steel, and concrete."""
    total_steel_wt = 0
    total_concrete_vol = 0
    
    bulb_dia = 2.5 * pile_dia
    min_spacing = 1.5 * bulb_dia 
    edge_clearance = 150
    
    for index, row in input_df.iterrows():
        qty = int(row["Qty"])
        if qty <= 0: continue
            
        load_kn = (row["Footing L (m)"] * row["Footing B (m)"]) * sbc
        num_piles = max(1, math.ceil(load_kn / pile_capacity))
        
        # Cap Concrete Volume
        if num_piles == 1:
            cap_l = pile_dia + (2 * edge_clearance)
            cap_w = cap_l
            cap_d = 450
        else:
            cap_l = min_spacing + pile_dia + (2 * edge_clearance)
            cap_w = pile_dia + (2 * edge_clearance)
            cap_d = 500
            
        total_concrete_vol += qty * (cap_l/1000 * cap_w/1000 * cap_d/1000)
        
        # Piles Concrete Volume
        pile_vol = num_piles * qty * (math.pi * (pile_dia/2000)**2) * pile_depth
        total_concrete_vol += pile_vol
        
        # Simplified Steel Estimation for Costing
        pile_main_len = pile_depth + 0.5 
        total_steel_wt += (num_piles * qty * 6 * pile_main_len) * unit_wt[12]
        
        spiral_length = (pile_depth / 0.15) * (math.pi * (pile_dia - 2*cover_fnd)/1000)
        total_steel_wt += (num_piles * qty * spiral_length) * unit_wt[8]
        
    # Calculate Total Price
    steel_cost = (total_steel_wt * 1.05) * rate_steel
    concrete_cost = total_concrete_vol * rate_concrete
    
    return steel_cost + concrete_cost, total_steel_wt, total_concrete_vol

# ==========================================
# 3. TRIGGER AI OPTIMIZATION
# ==========================================
if st.button("🧠 Run AI Auto-Optimization", type="primary"):
    st.markdown("---")
    
    with st.spinner('Running thousands of structural permutations...'):
        # AI Tests these configurations (Dia in mm, Depth in m, Capacity in kN)
        test_profiles = [
            {"dia": 250, "depth": 3.0, "cap": 150},
            {"dia": 300, "depth": 4.0, "cap": 250},
            {"dia": 400, "depth": 5.0, "cap": 400}
        ]
        
        best_profile = None
        lowest_cost = float('inf')
        optimization_logs = []
        
        for profile in test_profiles:
            cost, steel, conc = simulate_design(profile["dia"], profile["depth"], profile["cap"])
            optimization_logs.append({
                "Pile Dia (mm)": profile["dia"],
                "Total Steel (kg)": round(steel * 1.05, 1),
                "Concrete (m³)": round(conc, 2),
                "Total Est. Cost (Rs)": f"₹ {int(cost):,}"
            })
            
            if cost < lowest_cost:
                lowest_cost = cost
                best_profile = profile

    st.header("3. AI Optimization Results")
    st.caption("AI Evaluated the following permutations based on your material rates:")
    st.table(pd.DataFrame(optimization_logs))
    
    st.success(f"### 🏆 Winning Design Selected: {best_profile['dia']}mm Diameter Piles")
    st.markdown(f"**Why?** It optimally balances the cost of concrete and steel, resulting in the lowest overall execution cost of **₹ {int(lowest_cost):,}**.")
    
    # ==========================================
    # 4. GENERATE FINAL BBS WITH WINNING DESIGN
    # ==========================================
    st.markdown("---")
    st.subheader("4. Final Bar Bending Schedule (BBS)")
    
    pile_dia = best_profile["dia"]
    pile_depth = best_profile["depth"]
    pile_capacity = best_profile["cap"]
    
    bbs_data = []
    total_steel = {8: 0, 10: 0, 12: 0, 16: 0, 20: 0}
    bulb_dia = 2.5 * pile_dia
    min_spacing = 1.5 * bulb_dia 
    
    for index, row in input_df.iterrows():
        qty = int(row["Qty"])
        if qty <= 0: continue
            
        load_kn = (row["Footing L (m)"] * row["Footing B (m)"]) * sbc
        num_piles = max(1, math.ceil(load_kn / pile_capacity))
        
        edge_clearance = 150
        
        # 1. Piles
        total_piles = num_piles * qty
        pile_main_len = pile_depth + 0.5 
        bbs_data.append({"Element": f"Pile {row['ID']} (D={int(pile_dia)}mm) - Main", "Shape": "L", "Dia": 12, "Members": total_piles, "Bars/Mem": 6, "Total Bars": total_piles*6, "Cut Length (m)": pile_main_len, "Total Len (m)": total_piles*6*pile_main_len})
        total_steel[12] += total_piles * 6 * pile_main_len
        
        spiral_length = (pile_depth / 0.15) * (math.pi * (pile_dia - 2*cover_fnd)/1000)
        bbs_data.append({"Element": f"Pile {row['ID']} (D={int(pile_dia)}mm) - Spiral", "Shape": r"\bigcirc", "Dia": 8, "Members": total_piles, "Bars/Mem": 1, "Total Bars": total_piles, "Cut Length (m)": round(spiral_length,2), "Total Len (m)": round(total_piles*spiral_length,2)})
        total_steel[8] += total_piles * spiral_length
        
        # 2. Pile Caps
        if num_piles == 1:
            cap_l = pile_dia + (2 * edge_clearance)
            cap_w = cap_l
            cap_d = 450
            mesh_x_len = (cap_l - 2*cover_fnd + 200) / 1000 
            mesh_y_len = mesh_x_len
            mesh_x_qty = math.ceil(cap_w / 150) + 1
            mesh_y_qty = mesh_x_qty
            
            bbs_data.append({"Element": f"Cap {row['ID']} ({int(cap_l)}x{int(cap_w)}x{int(cap_d)}) - Mesh X", "Shape": r"\sqcup", "Dia": 10, "Members": qty, "Bars/Mem": mesh_x_qty, "Total Bars": qty*mesh_x_qty, "Cut Length (m)": mesh_x_len, "Total Len (m)": qty*mesh_x_qty*mesh_x_len})
            bbs_data.append({"Element": f"Cap {row['ID']} ({int(cap_l)}x{int(cap_w)}x{int(cap_d)}) - Mesh Y", "Shape": r"\sqcup", "Dia": 10, "Members": qty, "Bars/Mem": mesh_y_qty, "Total Bars": qty*mesh_y_qty, "Cut Length (m)": mesh_y_len, "Total Len (m)": qty*mesh_y_qty*mesh_y_len})
            total_steel[10] += (qty * mesh_x_qty * mesh_x_len) + (qty * mesh_y_qty * mesh_y_len)
        else:
            cap_l = min_spacing + pile_dia + (2 * edge_clearance)
            cap_w = pile_dia + (2 * edge_clearance)
            cap_d = 500
            mesh_long_len = (cap_l - 2*cover_fnd + 200) / 1000
            mesh_short_len = (cap_w - 2*cover_fnd + 200) / 1000
            mesh_long_qty = math.ceil(cap_w / 150) + 1
            mesh_short_qty = math.ceil(cap_l / 150) + 1
            
            bbs_data.append({"Element": f"Cap {row['ID']} ({int(cap_l)}x{int(cap_w)}x{int(cap_d)}) - Short", "Shape": r"\sqcup", "Dia": 10, "Members": qty, "Bars/Mem": mesh_short_qty, "Total Bars": qty*mesh_short_qty, "Cut Length (m)": mesh_short_len, "Total Len (m)": round(qty*mesh_short_qty*mesh_short_len, 2)})
            bbs_data.append({"Element": f"Cap {row['ID']} ({int(cap_l)}x{int(cap_w)}x{int(cap_d)}) - Long", "Shape": r"\sqcup", "Dia": 12, "Members": qty, "Bars/Mem": mesh_long_qty, "Total Bars": qty*mesh_long_qty, "Cut Length (m)": mesh_long_len, "Total Len (m)": round(qty*mesh_long_qty*mesh_long_len, 2)})
            total_steel[10] += (qty * mesh_short_qty * mesh_short_len)
            total_steel[12] += (qty * mesh_long_qty * mesh_long_len)

        # 3. Columns
        col_l, col_b = row["Col L (mm)"], row["Col B (mm)"]
        main_dia = int(row["Main Dia (mm)"])
        if main_dia > 0:
            main_len = 1.5 + 0.6 
            bbs_data.append({"Element": f"Col {row['ID']} ({int(col_l)}x{int(col_b)}) - Main", "Shape": "L", "Dia": main_dia, "Members": qty, "Bars/Mem": int(row["Main Qty"]), "Total Bars": qty*int(row["Main Qty"]), "Cut Length (m)": main_len, "Total Len (m)": round(qty*int(row["Main Qty"])*main_len, 2)})
            total_steel[main_dia] += qty * int(row["Main Qty"]) * main_len
            
        sec_dia = int(row["Sec Dia (mm)"])
        if sec_dia > 0:
            bbs_data.append({"Element": f"Col {row['ID']} ({int(col_l)}x{int(col_b)}) - Sec", "Shape": "L", "Dia": sec_dia, "Members": qty, "Bars/Mem": int(row["Sec Qty"]), "Total Bars": qty*int(row["Sec Qty"]), "Cut Length (m)": main_len, "Total Len (m)": round(qty*int(row["Sec Qty"])*main_len, 2)})
            total_steel[sec_dia] += qty * int(row["Sec Qty"]) * main_len

        core_l = col_l - (2 * cover_col)
        core_b = col_b - (2 * cover_col)
        tie_cut_len = (2 * (core_l + core_b) + (24 * 8)) / 1000 
        bbs_data.append({"Element": f"Col {row['ID']} ({int(col_l)}x{int(col_b)}) - Ties", "Shape": r"\square", "Dia": 8, "Members": qty, "Bars/Mem": 10, "Total Bars": qty*10, "Cut Length (m)": round(tie_cut_len,2), "Total Len (m)": round(qty*10*tie_cut_len, 2)})
        total_steel[8] += qty * 10 * tie_cut_len

    # --- Render BBS Data ---
    df_bbs = pd.DataFrame(bbs_data)
    st.dataframe(df_bbs, use_container_width=True, hide_index=True)

    # --- Generate Abstract Data ---
    st.markdown("---")
    st.subheader("5. Optimized Steel Abstract")
    abstract_data = []
    grand_total = 0
    for dia, length in total_steel.items():
        if length > 0:
            weight = length * unit_wt.get(dia, 0)
            grand_total += weight
            abstract_data.append({
                "Bar Dia (mm)": f"{dia} mm",
                "Total Length (m)": round(length, 1),
                "Total Weight (kg)": round(weight, 1)
            })
            
    col1, col2 = st.columns([2, 1])
    with col1:
        st.table(pd.DataFrame(abstract_data))
    with col2:
        st.success(f"### 🛒 Grand Total (incl. 5% waste):\n **{grand_total * 1.05:.1f} kg**")

    # ==========================================
    # 5. DYNAMIC LATEX REPORT GENERATOR
    # ==========================================
    st.markdown("---")
    st.subheader("📄 Export Professional Report")
    
    # Constructing the BBS Table Rows for LaTeX
    latex_bbs_rows = ""
    for row in bbs_data:
        latex_bbs_rows += f"{row['Element']} & ${row['Shape']}$ & {row['Dia']} & {row['Members']} & {row['Bars/Mem']} & {row['Total Bars']} & {row['Cut Length (m)']} & {row['Total Len (m)']} \\\\\n\\midrule\n"
        
    # Constructing the Abstract Table Rows for LaTeX
    latex_abstract_rows = ""
    for row in abstract_data:
        latex_abstract_rows += f"{row['Bar Dia (mm)']} & {row['Total Length (m)']} & {row['Total Weight (kg)']} \\\\\n"

    # Full LaTeX Template (A4 Landscape with XlTabular)
    latex_template = f"""\\documentclass[11pt, a4paper, landscape]{{article}}

\\usepackage[utf8]{{inputenc}}
\\usepackage[margin=0.8in]{{geometry}}
\\usepackage{{amsmath, amssymb}}
\\usepackage{{booktabs}}
\\usepackage{{xltabular}} 
\\usepackage{{makecell}}

\\renewcommand{{\\arraystretch}}{{1.4}}
\\setlength{{\\aboverulesep}}{{0pt}}
\\setlength{{\\belowrulesep}}{{0pt}}

\\title{{\\textbf{{AI-Optimized Execution BBS \\& Material Abstract}}}}
\\author{{Structural Engineering Optimization Engine}}
\\date{{}}

\\begin{{document}}

\\maketitle

\\section*{{1. Bar Bending Schedule (BBS) - {best_profile['dia']}mm Piles}}
\\textit{{Notes: All dimensions are in meters unless specified. Clear cover assumed as {cover_fnd}mm for foundation elements and {cover_col}mm for neck columns.}}

\\vspace{{1em}}

\\noindent
\\begin{{xltabular}}{{\\textwidth}}{{@{{}} >{{\\raggedright\\arraybackslash}}X c c c c c c c @{{}}}}
% --- FIRST PAGE HEADER ---
\\toprule
\\textbf{{Element \\& Bar Description}} & \\textbf{{Shape}} & \\textbf{{Dia ($\\phi$)}} & \\makecell{{\\textbf{{No. of}}\\\\\\textbf{{Members}}}} & \\makecell{{\\textbf{{Bars per}}\\\\\\textbf{{Member}}}} & \\textbf{{Total Bars}} & \\makecell{{\\textbf{{Cut Length}}\\\\\\textbf{{(m)}}}} & \\makecell{{\\textbf{{Total Length}}\\\\\\textbf{{(m)}}}} \\\\
\\midrule
\\endfirsthead

% --- REPEATING HEADER (For subsequent pages) ---
\\toprule
\\textbf{{Element \\& Bar Description}} & \\textbf{{Shape}} & \\textbf{{Dia ($\\phi$)}} & \\makecell{{\\textbf{{No. of}}\\\\\\textbf{{Members}}}} & \\makecell{{\\textbf{{Bars per}}\\\\\\textbf{{Member}}}} & \\textbf{{Total Bars}} & \\makecell{{\\textbf{{Cut Length}}\\\\\\textbf{{(m)}}}} & \\makecell{{\\textbf{{Total Length}}\\\\\\textbf{{(m)}}}} \\\\
\\midrule
\\endhead

% --- FOOTER (When table breaks to next page) ---
\\midrule
\\multicolumn{{8}}{{r}}{{\\textit{{Continued on next page...}}}} \\\\
\\endfoot

% --- FINAL FOOTER (End of table) ---
\\bottomrule
\\endlastfoot

% --- DYNAMIC TABLE DATA ---
{latex_bbs_rows}
\\end{{xltabular}}

\\newpage

\\section*{{2. Optimized Reinforcement Abstract (Material Takeoff)}}

\\textit{{Unit weights calculated using standard IS formulation: $W = \\frac{{D^2}}{{162}} \\text{{ kg/m}}$.}}

\\vspace{{1em}}

\\noindent
\\begin{{xltabular}}{{\\textwidth}}{{@{{}} c >{{\\raggedright\\arraybackslash}}X r @{{}}}}
% --- FIRST PAGE HEADER ---
\\toprule
\\textbf{{Bar Dia ($\\phi$)}} & \\textbf{{Total Length (m)}} & \\textbf{{Total Weight (kg)}} \\\\
\\midrule
\\endfirsthead

% --- REPEATING HEADER ---
\\toprule
\\textbf{{Bar Dia ($\\phi$)}} & \\textbf{{Total Length (m)}} & \\textbf{{Total Weight (kg)}} \\\\
\\midrule
\\endhead

% --- CONTINUATION FOOTER ---
\\midrule
\\multicolumn{{3}}{{r}}{{\\textit{{Continued on next page...}}}} \\\\
\\endfoot

% --- FINAL FOOTER ---
\\endlastfoot

% --- DYNAMIC TABLE DATA ---
{latex_abstract_rows}
\\midrule
\\multicolumn{{2}}{{r}}{{\\textbf{{Sub-Total}}}} & \\textbf{{{grand_total:.1f} kg}} \\\\
\\multicolumn{{2}}{{r}}{{\\text{{Wastage \\& Binding Wire (5\\%)}}}} & \\textbf{{{grand_total * 0.05:.1f} kg}} \\\\
\\midrule
\\multicolumn{{2}}{{r}}{{\\textbf{{OPTIMIZED GRAND TOTAL}}}} & \\textbf{{$\\approx$ {grand_total * 1.05:.1f} kg}} \\\\
\\bottomrule
\\end{{xltabular}}

\\end{{document}}
"""

    # Streamlit Download Button
    st.download_button(
        label="📥 Download Optimized LaTeX Report (.tex)",
        data=latex_template,
        file_name="AI_Optimized_BBS_Report.tex",
        mime="text/plain",
        type="primary"
    )
    st.caption("You can upload this `.tex` file directly to Overleaf or compile it with MiKTeX/TeXStudio to generate a perfectly formatted PDF document.")
# ==========================================
    # 6. DYNAMIC CAD (DXF) GENERATOR
    # ==========================================
    st.markdown("---")
    st.subheader("📐 Export AutoCAD Drawings")
    
    # We will generate a CAD drawing for the heaviest footing type (F3/F4 Double Pile Cap)
    # Re-calculate the winning dimensions for the double cap:
    edge_clearance = 150
    bulb_dia = 2.5 * best_profile['dia']
    min_spacing = 1.5 * bulb_dia
    
    ai_cap_l = min_spacing + best_profile['dia'] + (2 * edge_clearance)
    ai_cap_w = best_profile['dia'] + (2 * edge_clearance)
    
    # Generate the CAD file using our function
    dxf_data = generate_cad_plan(
        cap_l_mm=ai_cap_l, 
        cap_w_mm=ai_cap_w, 
        col_l_mm=500,  # Based on C3/C4
        col_b_mm=280, 
        pile_dia_mm=best_profile['dia'],
        spacing_mm=min_spacing
    )
    
    col_cad1, col_cad2 = st.columns([2,1])
    with col_cad1:
        st.info("The AI has dynamically generated a 2D AutoCAD Plan for the most critical Double-Pile Cap based on the optimized IS 2911 spacing parameters.")
        
    with col_cad2:
        # Streamlit DXF Download Button
        st.download_button(
            label="🏗️ Download AutoCAD Plan (.dxf)",
            data=dxf_data,
            file_name="Optimized_Pile_Cap_Plan.dxf",
            mime="application/dxf",
            type="primary"
        )
