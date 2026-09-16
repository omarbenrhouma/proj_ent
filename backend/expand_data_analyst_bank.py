"""Build a 100-question Data Analyst bank and three equivalent versions."""
from app.db import SessionLocal
from app.models import Campaign, Category, Difficulty, Question, QuestionStatus, QuestionType, Skill, TestVersion, TestVersionQuestion

SQL = ["INNER JOIN", "LEFT JOIN", "GROUP BY", "HAVING", "WHERE", "COUNT(DISTINCT)", "CASE WHEN", "CTE", "ROW_NUMBER", "COALESCE", "NULLIF", "UNION ALL", "DATE_TRUNC", "LAG", "LEAD", "INDEX", "PRIMARY KEY", "FOREIGN KEY"]
METRICS = ["taux de conversion", "panier moyen", "rétention client", "churn", "marge brute", "coût d'acquisition", "valeur vie client", "taux de rebond", "revenu récurrent", "part de marché", "satisfaction client", "délai de livraison", "taux de retour", "taux d'activation", "croissance mensuelle", "taux d'erreur", "disponibilité", "taux de complétion"]

def option(correct): return [{"key":"A","label":correct,"correct":True},{"key":"B","label":"Une mesure sans lien avec la question","correct":False},{"key":"C","label":"Une valeur choisie au hasard","correct":False},{"key":"D","label":"Une donnée non vérifiée","correct":False}]

def run():
 db=SessionLocal()
 try:
  campaign=db.query(Campaign).filter_by(active=True).first()
  if not campaign:
   campaign=Campaign(name="Évaluation Data Analyst",job_title="Data Analyst",duration_seconds=2700,show_result_to_candidate=True,active=True); db.add(campaign); db.flush()
  cats={c.code:c for c in db.query(Category).filter(Category.code.in_(["TECHNIQUE","LOGIQUE","GENERAL"])).all()}
  skills={}
  for code,name in [("TECHNIQUE","SQL et analyse"),("LOGIQUE","Raisonnement analytique"),("GENERAL","Métier et communication")]:
   s=db.query(Skill).filter_by(name=name).first() or Skill(name=name,category_id=cats[code].id); db.add(s); db.flush(); skills[code]=s
  items=[]
  for term in SQL:
   items.append(("TECHNIQUE",f"Dans une analyse de données, à quoi sert principalement {term} ?",f"Appliquer correctement {term} pour produire un résultat fiable"))
  for n,metric in enumerate(METRICS,1):
   items.append(("TECHNIQUE",f"Quel contrôle est essentiel avant de communiquer le {metric} ?",f"Vérifier la période, la définition et la qualité des données"))
  for n in range(18):
   a=n+2; seq=[a,a*2,a*4]; items.append(("LOGIQUE",f"Complétez la suite : {seq[0]}, {seq[1]}, {seq[2]}, …",str(a*8)))
  for code,statement,answer in items:
   if not db.query(Question).filter_by(statement=statement).first():
    q=Question(category_id=cats[code].id,skill_id=skills[code].id,difficulty=Difficulty.MEDIUM,question_type=QuestionType.SINGLE_CHOICE,statement=statement,points=2,status=QuestionStatus.VALIDATED,options=option(answer)); db.add(q)
  db.flush(); questions=db.query(Question).filter(Question.status==QuestionStatus.VALIDATED).order_by(Question.id).all()[:100]
  by_category={code:[q for q in questions if q.category_id==cats[code].id] for code in cats}
  blueprints={"A":{"TECHNIQUE":14,"LOGIQUE":11,"GENERAL":8},"B":{"TECHNIQUE":14,"LOGIQUE":11,"GENERAL":8},"C":{"TECHNIQUE":14,"LOGIQUE":11,"GENERAL":9}}
  for version_index, code in enumerate(["A","B","C"]):
   v=db.query(TestVersion).filter_by(campaign_id=campaign.id,code=code).first()
   if not v: v=TestVersion(campaign_id=campaign.id,code=code,duration_seconds=2700,published=code=="A"); db.add(v); db.flush()
   v.questions.clear(); db.flush(); selected=[]
   for category_code,count in blueprints[code].items():
    pool=by_category[category_code]; start=(version_index*count)%len(pool)
    selected.extend((pool+pool)[start:start+count])
   # Keep each section continuous: technical, then logic, then business/general.
   grouped={category_code:[q for q in selected if q.category_id==cats[category_code].id] for category_code in blueprints[code]}
   selected=grouped["TECHNIQUE"] + grouped["LOGIQUE"] + grouped["GENERAL"]
   for pos,q in enumerate(selected,1): v.questions.append(TestVersionQuestion(question_id=q.id,position=pos,points=q.points))
  db.commit(); print(len(questions),"questions; 3 versions created")
 finally: db.close()
if __name__=='__main__': run()
