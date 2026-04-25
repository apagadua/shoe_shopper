# Shoe Shopping App \- Categorization Structure

Users navigate to shoes via two paths: **Function** (use case) or **Silhouette** (physical appearance). Each shoe is tagged with both.

## FUNCTION PATH

Navigation based on intended use/purpose of the shoe.

### 1\. Athletic

- **Running**  
  - Road  
  - Trail  
  - Indoor/Track  
- **Training**  
- **Basketball**  
- **Field Sports**  
  - Soccer  
  - Football  
  - Lacrosse  
- **Tennis**  
- **Skate**  
- **Hiking**

### 2\. Casual

- **Sneakers**  
- **Boots**  
- **Slip-ons**

### 3\. Work

- **Indoor**  
- **Outdoor**

### 4\. Formal

## 

## SILHOUETTE PATH

Navigation based on physical appearance/style of the shoe.

### 1\. Boot

- **Chelsea**  
- **Chukka**  
- **Moc Toe**  
- **Hiking**  
- **Work**  
- **Combat**  
- **Dress**

### 2\. Sneaker

- **Low-top**  
  - Athletic  
  - Casual  
  - Skate  
- **High-top**  
  - Athletic  
  - Casual  
  - Skate  
- **Slip-on Sneaker**

### 3\. Slip-on

- **Loafer**  
- **Clog**

### 4\. Dress Shoe

## FILTERS/ATTRIBUTES

Applied after category selection to refine results.

- **Waterproof** (yes/no)  
- **Vegan** (yes/no)  
- **Leather** (yes/no)  
- **Resoleable** (yes/no)  
- **Insulated** (yes/no)  
- **Slip-resistant** (yes/no)  
- **Color Options**  
- **Brand**

## Implementation Notes

Each shoe needs:

- One or more Function path tags  
- One or more Silhouette path tags  
- Applicable attribute flags

### Example: Altra Lone Peak 7

- **Function:** Athletic → Running → Trail  
- **Silhouette:** Sneaker → Low-top → Athletic  
- **Attributes:** Vegan, slip-resistant

### Example: Danner Bull Run

- **Function:** Work → Outdoor, Casual → Boots  
- **Silhouette:** Boot → Moc Toe  
- **Attributes:** Leather, resoleable, slip-resistant

