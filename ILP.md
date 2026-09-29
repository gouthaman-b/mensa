# Meal Planning ILP Model

This document explains the optimization model used in the meal planner implemented in [src/mensa/ilp.py](src/mensa/ilp.py).

The result is a binary optimization problem with one decision variable per eligible meal and a set of linear constraints describing the user’s needs and preferences.

## Variables

The planner decides, for each eligible meal, whether it should be included in the final menu.

For each candidate meal $i$, we define a binary decision variable:

$$
x_i =
\begin{cases}
1 & \text{if meal } i \text{ is selected} \\
0 & \text{if meal } i \text{ is not selected}
\end{cases}
$$

So each meal is either chosen or not chosen.

---

## Objective

The planner tries to choose the best set of meals while minimizing two things at once:

- total price
- total sustainability score

The objective is:

$$
\min \quad w_p \sum_{i=1}^{n} p_i x_i + w_s \sum_{i=1}^{n} s_i x_i
$$

Where:

- $p_i$ = price of meal $i$ for the chosen user role
- $s_i$ = sustainability score of meal $i$
- $w_p$ = price weight from the user preferences
- $w_s$ = sustainability weight from the user preferences

In plain language: the model prefers cheaper meals, but it also tries to avoid meals with poor sustainability scores. The relative importance of price versus sustainability is controlled by the user’s weights.

---

## Constraints

### 1A. One main meal per day

For each day $d$, there must be exactly one main meal selected:

$$
\sum_{i \in \text{Main}(d)} x_i = 1
$$

This ensures every day has a complete main choice.

### 1B. Breakfast rule

For each day $d$:

- if the user wants breakfast, then exactly one breakfast must be selected:

$$
\sum_{i \in \text{Breakfast}(d)} x_i = 1
$$

- otherwise, breakfast is optional and at most one breakfast may be chosen:

$$
\sum_{i \in \text{Breakfast}(d)} x_i \le 1
$$

### 1C. Side rule

For each day $d$:

- if the user wants a side, then exactly one side must be selected:

$$
\sum_{i \in \text{Side}(d)} x_i = 1
$$

- otherwise, at most one side may be chosen:

$$
\sum_{i \in \text{Side}(d)} x_i \le 1
$$

---

## 2. Budget constraints

### Total budget

If the user gives a total budget cap, then the total selected meal price cannot exceed it:

$$
\sum_{i=1}^{n} p_i x_i \le B_{total}
$$

### Daily budget

If the user gives a per-day budget cap, then for each day $d$:

$$
\sum_{i \in \text{Meals}(d)} p_i x_i \le B_{day}
$$

This keeps the spend under control each day as well as over the whole plan.

---

## 3. Repetition and sustainability caps

### A. Category repetition limit

If the user specifies a maximum number of repeats for a category, then for each category $c$:

$$
\sum_{i \in \text{Main},\; category(i)=c} x_i \le cap_c
$$

This prevents the planner from repeatedly choosing too many meals from the same type or dietary category.

### B. Average sustainability cap

If a sustainability ceiling is set, the planner keeps the total sustainability burden from main meals under a daily threshold:

$$
\sum_{i \in \text{Main}} s_i x_i \le S_{max} \cdot D
$$

where $D$ is the number of days in the plan.

---

## 4. Nutrition constraints

The planner also enforces daily nutrition limits. For each day $d$, it checks the total selected nutritional content of meals on that day.


*Note*: The current API responses have the nutrition values set to null.

### Calories

If a minimum is required:

$$
\sum_{i \in \text{Meals}(d)} cal_i x_i \ge L_{cal}
$$

If a maximum is required:

$$
\sum_{i \in \text{Meals}(d)} cal_i x_i \le U_{cal}
$$

### Sugar, saturated fat, and salt

These are upper bounds:

$$
\sum_{i \in \text{Meals}(d)} sugar_i x_i \le U_{sugar}
$$

$$
\sum_{i \in \text{Meals}(d)} fat_i x_i \le U_{fat}
$$

$$
\sum_{i \in \text{Meals}(d)} salt_i x_i \le U_{salt}
$$

### Protein

If a minimum protein target is required:

$$
\sum_{i \in \text{Meals}(d)} prot_i x_i \ge L_{protein}
$$

So the model is not only trying to minimize cost; it is also maintaining a healthy daily nutrition profile.

---

##  Feasibility filters before optimization

Before building the actual optimization model, the solver removes meals that are invalid for the user. It excludes meals if they:

- have no valid price for the chosen role
- are in exclusion list
- contain allergens the user wants to avoid
- do not satisfy the selected dietary preference

If no valid meal remains, the model reports an infeasible plan.

---


