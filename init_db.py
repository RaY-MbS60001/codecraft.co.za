# init_db.py
from app import app, db
from models import User, LearnshipEmail

def init_database():
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Check if admin user exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            # Create default admin user
            admin = User(
                email='admin@codecraftco.com',
                username='admin',
                full_name='System Administrator',
                role='admin',
                auth_method='credentials',
                is_active=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully!")
            print("Username: admin")
            print("Password: admin123")
        else:
            print("Admin user already exists!")
        
        print("Database initialized successfully!")

def init_learnership_emails():
    """Initialize the database with learnership email addresses"""
    with app.app_context():
        # Check if emails already exist
        if LearnshipEmail.query.first() is not None:
            print("Learnership emails already exist in database. Skipping initialization.")
            return
        
        # List of email addresses with company names
        email_data = [
            {"company_name": "Test ()", "email": "sfisomabaso12242001@gmail.com"},
            {"company_name": "Diversity Empowerment", "email": "Info@diversityempowerment.co.za"},
            {"company_name": "Sparrow Portal", "email": "Enquiries@sparrowportal.co.za"},
            {"company_name": "Impactful", "email": "Sihle.Nyanga@impactful.co.za"},
            {"company_name": "CSG Skills", "email": "mseleke@csgskills.co.za"},
            {"company_name": "AFREC", "email": "Consultant@afrec.co.za"},
            {"company_name": "Vision Academy", "email": "recruit@visionacademy.co.za"},
            {"company_name": "The Skills Hub", "email": "info@theskillshub.co.za"},
            {"company_name": "Rivoningo Consultancy", "email": "careers@rivoningoconsultancy.co.za"},
            {"company_name": "OKS", "email": "Recruitment@oks.co.za"},
            {"company_name": "I-Fundi", "email": "Farina.bowen@i-fundi.com"},
            {"company_name": "MSC", "email": "za031-cvapplications@msc.com"},
            {"company_name": "Liberty College", "email": "Funda@liberty-college.co.za"},
            {"company_name": "Sisekelo", "email": "ayandam@sisekelo.co.za"},
            {"company_name": "AAAT", "email": "apply@aaat.co.za"},
            {"company_name": "Learn SETA", "email": "hr@learnseta.online"},
            {"company_name": "Amphisa", "email": "tigane@amphisa.co.za"},
            {"company_name": "AfriSam", "email": "cm.gpnorthaggregate@za.afrisam.com"},
            {"company_name": "iLearn", "email": "tinyikom@ilearn.co.za"},
            {"company_name": "TechTISA", "email": "prabashini@techtisa.co.za"},
            {"company_name": "Fitho", "email": "cv@fitho.co.za"},
            {"company_name": "Training Force", "email": "Application@trainingforce.co.za"},
            {"company_name": "Tidy Swip", "email": "Learnerships@tidyswip.co.za"},
            {"company_name": "Nthuse Foundation", "email": "brandons@nthusefoundation.co.za"},
            {"company_name": "Ample Recruitment", "email": "cv@amplerecruitment.co.za"},
            {"company_name": "I-People", "email": "cv@i-people.co.za"},
            {"company_name": "FACT SA", "email": "recruitment3@factsa.co.za"},
            {"company_name": "IKWorx", "email": "recruitment@ikworx.co.za"},
            {"company_name": "APD JHB", "email": "recruitment@apdjhb.co.za"},
            {"company_name": "Skill Tech SA", "email": "query@skilltechsa.co.za"},
            {"company_name": "Camblish", "email": "qualitycontrol@camblish.co.za"},
            {"company_name": "BPC HR Solutions", "email": "Queen@bpchrsolutions.co.za"},
            {"company_name": "CTU Training", "email": "walter.mngomezulu@ctutraining.co.za"},
            {"company_name": "U-Belong", "email": "work@u-belong.co.za"},
            {"company_name": "eStudy SA", "email": "recruitment@estudysa.co.za"},
            {"company_name": "Zigna Training Online", "email": "ayo@zignatrainingonline.co.za"},
            {"company_name": "CDPA", "email": "amelia@cdpa.co.za"},
            {"company_name": "AFREC", "email": "Cv@afrec.co.za"},
            {"company_name": "AFREC", "email": "recruit@afrec.co.za"},
            {"company_name": "AFREC", "email": "recruitment@afrec.co.za"},
            {"company_name": "AFREC", "email": "Cvs@afrec.co.za"},
            {"company_name": "Bidvest Catering", "email": "Training2@bidvestcatering.co.za"},
            {"company_name": "CDA Solutions", "email": "faith.khethani@cdasolutions.co.za"},
            {"company_name": "Tiger Brands", "email": "Culinary.Recruitment@tigerbrands.com"},
            {"company_name": "Telebest", "email": "learners@telebest.co.za"},
            {"company_name": "Access4All SA", "email": "ginab@access4all-sa.co.za"},
            {"company_name": "GLU", "email": "cv@glu.co.za"},
            {"company_name": "GLU", "email": "ilze@glu.co.za"},
            {"company_name": "CSS Solutions", "email": "csshr@csssolutions.co.za"},
            {"company_name": "Advanced Assessments", "email": "genevieve@advancedassessments.co.za"},
            {"company_name": "AAAT", "email": "Jonas@aaat.co.za"},
            {"company_name": "Prime Serv", "email": "Infoct@primeserv.co.za"},
            {"company_name": "TE Academy", "email": "recruitmentofficer@teacademy.co.za"},
            {"company_name": "Retshepeng", "email": "training@retshepeng.co.za"},
            {"company_name": "KDS Training", "email": "Recruitment@kdstraining.co.za"},
            {"company_name": "Cowhirla Academy", "email": "learn@cowhirlacademy.co.za"},
            {"company_name": "Roah Consulting", "email": "recruitment@roahconsulting.co.za"},
            {"company_name": "Kboneng Consulting", "email": "admin@kbonengconsulting.co.za"},
            {"company_name": "NZ Consultants", "email": "victory@nzconsultancts.co.za"},
            {"company_name": "AAAT", "email": "Leratomoraba@aaat.co.za"},
            {"company_name": "Stratism", "email": "learnership@stratism.co.za"},
            {"company_name": "MPower Smart", "email": "recruitment@mpowersmart.co.za"},
            {"company_name": "Afrika Tikkun", "email": "LucyC@afrikatikkun.org"},
            {"company_name": "WeThinkCode", "email": "Info@wethinkcode.co.za"},
            {"company_name": "B School", "email": "justice.seupe@bschool.edu.za"},
            {"company_name": "TE Academy", "email": "sdf1@teacademy.co.za"},
            {"company_name": "African Bank", "email": "NMakazi@afrikanbank.co.za"},
            {"company_name": "Blind SA", "email": "trainingcentre.admin@blindsa.org.za"},
            {"company_name": "Pro-Learn", "email": "data.admin@pro-learn.co.za"},
            {"company_name": "Skills Junction", "email": "learnerships@skillsjunction.co.za"},
            {"company_name": "Friends 4 Life", "email": "achievement@friends4life.co.za"},
            {"company_name": "Dial A Dude", "email": "hr@dialadude.co.za"},
            {"company_name": "IBM SkillsBuild", "email": "ibmskillsbuild.emea@skilluponline.com"},
            {"company_name": "Snergy", "email": "info@snergy.co.za"},
            {"company_name": "SA Entrepreneurship Empowerment", "email": "samukelo@saentrepreneurshipempowerment.org.za"},
            {"company_name": "Signa", "email": "yes@signa.co.za"},
            {"company_name": "Edu-Wize", "email": "info@edu-wize.co.za"},
            {"company_name": "Edu-Wize", "email": "elsie@edu-wize.co.za"},
            {"company_name": "4YS", "email": "recruit@4ys.co.za"},
            {"company_name": "LeapCo", "email": "olwethu@leapco.co.za"},
            {"company_name": "LeapCo", "email": "Offer@leapco.co.za"},
            {"company_name": "Learnex", "email": "cv@learnex.co.za"},
            {"company_name": "Innovation Advance", "email": "hello@innovationadvance.co.za"},
            {"company_name": "Dynamic DNA", "email": "Talent@dynamicdna.co.za"},
            {"company_name": "NCPD", "email": "nombulelo@ncpd.org.za"},
            {"company_name": "Siyaya Skills", "email": "lebohang.matlala@siyayaskills.co.za"},
            {"company_name": "Transcend", "email": "learnerships@transcend.co.za"},
            {"company_name": "iLearn", "email": "Vusumuzig@ilearn.co.za"},
            {"company_name": "Barnne", "email": "cv@barnne.com"},
            {"company_name": "SASSETA", "email": "recruitment@sasseta.org"},
            {"company_name": "WPX Solutions", "email": "hr@wpxsolutions.com"},
            {"company_name": "Amphisa", "email": "Kruger@amphisa.co.za"},
            {"company_name": "TIHSA", "email": "faneleg@tihsa.co.za"},
            {"company_name": "Afrika Tikkun", "email": "pokellom@afrikatikkun.org"},
            {"company_name": "Swift Skills Academy", "email": "recruitment@swiftskillsacademy.co.za"},
            {"company_name": "Skills Panda", "email": "refiloe@skillspanda.co.za"},
            {"company_name": "ICAN SA", "email": "Nalini.cuppusamy@ican-sa.co.za"},
            {"company_name": "GCC-SD", "email": "placements@gcc-sd.com"},
            {"company_name": "EH Hassim", "email": "trainingcenter@ehhassim.co.za"},
            {"company_name": "Anova Health", "email": "Recruitment-parktown@anovahealth.co.za"},
            {"company_name": "iLearn", "email": "tshepisom@ilearn.co.za"},
            {"company_name": "Moonstone Info", "email": "faisexam@moonstoneinfo.co.za"},
            {"company_name": "Phosaane", "email": "recruitment@phosaane.co.za"},
            {"company_name": "Lethatsi PTY LTD", "email": "Luzuko@lethatsiptyltd.co.za"},
            {"company_name": "CBM Training", "email": "info@cbm-training.co.za"},
            {"company_name": "Bradshaw Leroux", "email": "Recruit@bradshawleroux.co.za"},
            {"company_name": "HRC Training", "email": "Info@Hrctraining.co.za"},
            {"company_name": "Bee Empowerment Services", "email": "Support@beeempowermentservices.co.za"},
            {"company_name": "Shimrag", "email": "lesegos@shimrag.co.za"},
            {"company_name": "TransUnion", "email": "Kgomotso.Modiba@transunion.com"},
            {"company_name": "Gijima", "email": "lebo.makgale@gijima.com"},
            {"company_name": "Eshy Brand", "email": "tumelo@eshybrand.co.za"},
            {"company_name": "Kunaku", "email": "learners@kunaku.co.za"},
            {"company_name": "Affinity Services", "email": "recruitment@affinityservices.co.za"},
            {"company_name": "CBM Training", "email": "Gugulethu@cbm-traning.co.za"},
            {"company_name": "TransUnion", "email": "GCCALearners@transunion.com"},
            {"company_name": "Quest College", "email": "Maria@questcollege.org.za"},
            {"company_name": "MI Centre", "email": "info@micentre.org.za"},
            {"company_name": "CBM Training", "email": "palesa@cbm-training.co.za"},
            {"company_name": "Consulting By Bongi", "email": "Info@consultingbybongi.com"},
            {"company_name": "Training Portal", "email": "learn@trainingportal.co.za"},
            {"company_name": "GCC-SD", "email": "info@gcc-sd.com"},
            {"company_name": "Retshepeng", "email": "Sales@retshepeng.co.za"},
            {"company_name": "Retshepeng", "email": "it@retshepeng.co.za"},
            {"company_name": "Tych", "email": "Precious@tych.co.za"},
            {"company_name": "Progression", "email": "farhana@progression.co.za"},
            {"company_name": "QASA", "email": "recruitment@qasa.co.za"},
            {"company_name": "TLO", "email": "Recruitment@tlo.co.za"},
            {"company_name": "Dibanisa Learning", "email": "Slindile@dibanisaleaening.co.za"},
            {"company_name": "Tric Talent", "email": "Anatte@trictalent.co.za"},
            {"company_name": "Novia One", "email": "Tai@noviaone.com"},
            {"company_name": "Edge Exec", "email": "kgotso@edgexec.co.za"},
            {"company_name": "Related Ed", "email": "kagiso@related-ed.com"},
            {"company_name": "RMA Education", "email": "Skills@rma.edu.co.za"},
            {"company_name": "Signa", "email": "nkhensani@signa.co.za"},
            {"company_name": "Learnex", "email": "joyce@learnex.co.za"},
            {"company_name": "XBO", "email": "cornelia@xbo.co.za"},
            {"company_name": "Nicasia Holdings", "email": "Primrose.mathe@nicasiaholdings.co.za"},
            {"company_name": "STS Africa", "email": "Recruitment@sts-africa.co.za"},
            {"company_name": "BSI Steel", "email": "Sifiso.ntamane@bsisteel.com"},
            {"company_name": "Progression", "email": "Recruitment@progression.co.za"},
            {"company_name": "Modern Centric", "email": "applications@moderncentric.co.za"},
            {"company_name": "Dynamic DNA", "email": "Smacaulay@dynamicdna.co.za"},
            {"company_name": "Dekra", "email": "reception@dekra.com"},
            {"company_name": "Quest College", "email": "patience@questcollege.org.za"},
            {"company_name": "Modern Centric", "email": "karenm@moderncentric.co.za"},
            {"company_name": "Octopi Renewed", "email": "IvyS@octopi-renewed.co.za"},
            {"company_name": "Eagle ESS", "email": "training2@eagle-ess.co.za"},
            {"company_name": "IBUSA", "email": "Mpumi.m@ibusa.co.za"},
            {"company_name": "RMV Solutions", "email": "Learnership@rmvsolutions.co.za"},
            {"company_name": "Talent Development", "email": "info@talentdevelooment.co.za"},
            {"company_name": "Transcend", "email": "unathi.mbiyoza@transcend.co.za"},
            {"company_name": "SEESA", "email": "helga@seesa.co.za"},
            {"company_name": "Skills Empire", "email": "admin@skillsempire.co.za"},
            {"company_name": "Foster Melliar", "email": "kutlwano.mothibe@fostermelliar.co.za"},
            {"company_name": "Alef Bet Learning", "email": "teddym@alefbetlearning.com"},
            {"company_name": "Pendula", "email": "rika@pendula.co.za"},
            {"company_name": "Siza Abantu", "email": "admin@sizaabantu.co.za"},
            {"company_name": "CBM Training", "email": "lorenzo@cbm-training.co.za"},
            {"company_name": "CBM Training", "email": "Winile@cbm-training.co.za"},
            {"company_name": "SERR", "email": "Maria@serr.co.za"},
            {"company_name": "CSG Skills", "email": "Sdube@csgskills.co.za"},
            {"company_name": "Modern Centric", "email": "kagisom@moderncentric.co.za"},
            {"company_name": "SITA", "email": "recruitment@sita.co.za"},
            {"company_name": "Mudi Training", "email": "kelvi.c@muditraining.co.za"},
            {"company_name": "Net Campus", "email": "Ntombi.Zondo@netcampus.com"},
            {"company_name": "Net Campus", "email": "Mary.carelse@netcampus.com"},
            {"company_name": "EduPower SA", "email": "divan@edupowersa.co.za"},
            {"company_name": "TLO", "email": "info@tlo.co.za"},
            {"company_name": "Liquor Barn", "email": "admin4@liquorbarn.co.za"},
            {"company_name": "King Rec", "email": "Zena@KingRec.co.za"},
            {"company_name": "Fennell", "email": "Hal@Fennell.co.za"},
            {"company_name": "SP Forge", "email": "Info@SpForge.co.za"},
            {"company_name": "Direct Axis", "email": "Careers@Directaxis.co.za"},
            {"company_name": "Benteler", "email": "Yasmin.theron@benteler.com"},
            {"company_name": "MASA", "email": "Pe@masa.co.za"},
            {"company_name": "MASA", "email": "Feziwe@masa.co.za"},
            {"company_name": "Adcorp Blu", "email": "Kasina.sithole@adcorpblu.com"},
            {"company_name": "Formex", "email": "enquiries@formex.co.za"},
            {"company_name": "Formex", "email": "byoyophali@formex.co.za"},
            {"company_name": "Q-Plas", "email": "Zandile@q-plas.co.za"},
            {"company_name": "Lumo Tech", "email": "contact@lumotech.co.za"},
            {"company_name": "Bel Essex", "email": "belcorp@belessex.co.za"},
            {"company_name": "Workforce", "email": "portelizabeth@workforce.co.za"},
            {"company_name": "Quest", "email": "lucilleh@quest.co.za"},
            {"company_name": "Top Personnel", "email": "reception@toppersonnel.co.za"},
            {"company_name": "MPC", "email": "rosanne@mpc.co.za"},
            {"company_name": "Online Personnel", "email": "claire@onlinepersonnel.co.za"},
            {"company_name": "Kelly", "email": "nicola.monsma@kelly.co.za"},
            {"company_name": "JR Recruitment", "email": "sandi@jrrecruitment.co.za"},
            {"company_name": "Ikamva Recruitment", "email": "nomsa@ikamvarecruitment.co.za"},
            {"company_name": "Abantu Staffing Solutions", "email": "tracy@abantustaffingsolutions.co.za"},
            {"company_name": "Alpha Labour", "email": "wayne@alphalabour.co.za"},
            {"company_name": "Thomas", "email": "jackiec@thomas.co.za"},
            {"company_name": "Capacity", "email": "nakitap@capacity.co.za"},
            {"company_name": "Colven", "email": "natalie@colven.co.za"},
            {"company_name": "Head Hunt", "email": "admin@headhunt.co.za"},
            {"company_name": "Icon", "email": "focus@icon.co.za"},
            {"company_name": "QS Africa", "email": "ADMIN@QSAFRICA.CO.ZA"},
            {"company_name": "CR Solutions", "email": "chantal@crsolutions.co.za"},
            {"company_name": "Bell Mark", "email": "zukiswa.nogqala@bell-mark.co.za"},
            {"company_name": "Pop Up", "email": "nokuthula.ndamase@popup.co.za"},
            {"company_name": "Seonnyatseng", "email": "Tsholofelo@seonyatseng.co.za"},
            {"company_name": "TN Electrical", "email": "info@tnelectrical.co.za"},
            {"company_name": "AAAA", "email": "adminb@aaaa.co.za"},
            {"company_name": "Ubuhle HR", "email": "reception@ubuhlehr.co.za"},
            {"company_name": "SITA", "email": "vettinginternship@sita.co.za"},
            {"company_name": "Careers IT", "email": "leanerships@careersit.co.za"},
            {"company_name": "TJH Business", "email": "melvin@tjhbusiness.co.za"},
            {"company_name": "Learner Sphere CD", "email": "recruitment@learnerspherecd.co.za"},
            {"company_name": "Odin Fin", "email": "alex@odinfin.co.za"},
            {"company_name": "Platinum Life", "email": "Manaka.Ramukuvhati@platinumlife.co.za"},
            {"company_name": "Seonnyatseng", "email": "info@seonyatseng.co.za"},
            {"company_name": "TLO", "email": "Application@tlo.co.za"},
            {"company_name": "Metanoia Group", "email": "Loren@metanoiagroup.co.za"},
            {"company_name": "Edu-Wize", "email": "r1@edu-wize.co.za"},
            {"company_name": "Advanced Assessments", "email": "recruitment@advancedassessments.co.za"},
            {"company_name": "Enpower", "email": "Angelique.haskins@enpower.co.za"},
            {"company_name": "ICAN SA", "email": "Jhbsourcing@ican-sa.co.za"},
            {"company_name": "Talent Development", "email": "Projects@talentdevelopment.co.za"},
            {"company_name": "Providing Skills", "email": "training1@providingskills.co.za"},
            {"company_name": "Providing Skills", "email": "thando@providingskills.co.za"},
            {"company_name": "Camblish", "email": "Info@camblish.co.za"},
            {"company_name": "Brightrock", "email": "Youniversity@brightrock.co.za"},
            {"company_name": "Heart Solutions", "email": "admin@heartsolutions.co.za"},
            {"company_name": "Star Schools", "email": "rnyoka@starschools.co.za"},
            {"company_name": "Modern Centric", "email": "malvinn@moderncentric.co.za"},
            {"company_name": "Skills Bureau", "email": "operations2@skillsbureau.co.za"},
            {"company_name": "Xtensive ICT", "email": "sphiwe@xtensiveict.co.za"},
            {"company_name": "Engen Oil", "email": "Learnerships@engenoil.com"},
            {"company_name": "GLU", "email": "ouma@glu.co.za"},
            {"company_name": "ICAN SA", "email": "Pretty.Dlamini@ican-sa.co.za"},
            {"company_name": "Vistech", "email": "skills@vistech.co.za"},
            {"company_name": "Gold Rush", "email": "mpho.moletsane@goldrurush.co.za"},
            {"company_name": "HCI Skills", "email": "recruitment@hciskills.co.za"},
            {"company_name": "PMI SA", "email": "boitumelo.makhubela@pmi-sa.co.za"},
            {"company_name": "Skills Bureau", "email": "talent@skillsbureau.co.za"},
            {"company_name": "Vital Online", "email": "training@vitalonline.co.za"},
            {"company_name": "Compare A Quote", "email": "Admin@compareaquote.co.za"},
            {"company_name": "Besec", "email": "cv@besec.co.za"},
            {"company_name": "eStudy SA", "email": "trainme@estudysa.co.za"},
            {"company_name": "Net Campus", "email": "info@netcampus.com"}
        ]
        
        # Add email addresses to the database
        for data in email_data:
            email = LearnshipEmail(company_name=data["company_name"], email=data["email"])
            db.session.add(email)
        
        db.session.commit()
        print(f"Added {len(email_data)} learnership emails to the database")

if __name__ == '__main__':
    init_database()
    
    # Also initialize learnership emails
    init_learnership_emails()