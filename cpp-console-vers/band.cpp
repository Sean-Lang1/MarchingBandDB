// THE MARCHING DATABASE (v1.2.0) - SQLite + C++ console app 
// Recent Updates: shirt/shoe sizes, uniforms sizes, etc
//
// Compile (Linux/Mac):
//   g++ band.cpp -o band -lsqlite3
//
// Run:
//   ./band

#include <cstdlib>
#include <sqlite3.h>
#include <iostream>
#include <string>
#include <limits>
#include <iomanip>
#include <vector>
#include <algorithm>
#include <cctype>

using namespace std;

sqlite3* db = nullptr;

static void clearInputLine() {
    cin.ignore(numeric_limits<streamsize>::max(), '\n');
}

static string trim(const string& s) {
    size_t a = 0, b = s.size();
    while (a < b && isspace((unsigned char)s[a])) a++;
    while (b > a && isspace((unsigned char)s[b - 1])) b--;
    return s.substr(a, b - a);
}

static string upperCopy(string s) {
    for (char& c : s) c = (char)toupper((unsigned char)c);
    return s;
}

static int readIntInRange(const string& prompt, int lo, int hi) {
    while (true) {
        cout << prompt;
        int x;
        if (cin >> x) {
            if (x >= lo && x <= hi) return x;
            cout << "Nope. Enter " << lo << "-" << hi << ".\n";
        } else {
            cout << "Nope. Enter a number please!.\n";
            cin.clear();
        }
        clearInputLine();
    }
}

static int readBool01(const string& prompt) {
    while (true) {
        cout << prompt;
        int x;
        if (cin >> x) {
            if (x == 0 || x == 1) return x;
            cout << "Nope. Enter 1 or 0, please.\n";
        } else {
            cout << "Nope. Enter 1 or 0, please.\n";
            cin.clear();
        }
        clearInputLine();
    }
}

static double readDoubleInRange(const string& prompt, double lo, double hi) {
    while (true) {
        cout << prompt;
        double x;
        if (cin >> x) {
            if (x >= lo && x <= hi) return x;
            cout << "Nope. Enter " << lo << "-" << hi << ".\n";
        } else {
            cout << "Nope. Enter a number.\n";
            cin.clear();
        }
        clearInputLine();
    }
}

static bool execSQL(const string& sql) {
    char* errMsg = nullptr;
    int rc = sqlite3_exec(db, sql.c_str(), nullptr, nullptr, &errMsg);
    if (rc != SQLITE_OK) {
        cout << "SQL error: " << (errMsg ? errMsg : "Unknown error") << "\n";
        sqlite3_free(errMsg);
        return false;
    }
    return true;
}

static const char* colText(sqlite3_stmt* s, int i) {
    const unsigned char* t = sqlite3_column_text(s, i);
    return t ? (const char*)t : "";
}

static bool studentExists(int studentId) {
    const char* sql = "SELECT 1 FROM STUDENTS WHERE STUDENT_ID=?;";
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK) return false;
    sqlite3_bind_int(stmt, 1, studentId);
    bool ok = (sqlite3_step(stmt) == SQLITE_ROW);
    sqlite3_finalize(stmt);
    return ok;
}

static bool getStudentSection(int studentId, string& outSection) {
    outSection = "";
    const char* sql = "SELECT SECTION FROM STUDENTS WHERE STUDENT_ID=?;";
    sqlite3_stmt* stmt = nullptr;

    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK) return false;
    sqlite3_bind_int(stmt, 1, studentId);

    bool ok = false;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        outSection = colText(stmt, 0);
        ok = true;
    }
    sqlite3_finalize(stmt);

    if (!ok) outSection = "";
    return ok;
}

static bool columnExists(const string& table, const string& col) {
    string sql = "PRAGMA table_info(" + table + ");";
    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db, sql.c_str(), -1, &stmt, nullptr) != SQLITE_OK) return false;

    bool found = false;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        string name = colText(stmt, 1); 
        if (upperCopy(name) == upperCopy(col)) {
            found = true;
            break;
        }
    }
    sqlite3_finalize(stmt);
    return found;
}

static string readSectionValidated(const string& prompt) {
    static const vector<string> allowed = {"WOODWIND","BRASS","PERCUSSION","AUXILIARY","DM"};
    while (true) {
        cout << prompt;
        string s;
        getline(cin, s);
        s = upperCopy(trim(s));

        if (find(allowed.begin(), allowed.end(), s) != allowed.end()) return s;

        cout << "Invalid selection. Please try again: WOODWIND, BRASS, PERCUSSION, AUXILIARY, DM.\n";
    }
}

static void ensureTables() {
    execSQL("PRAGMA foreign_keys = ON;");

    execSQL(
        "CREATE TABLE IF NOT EXISTS STUDENTS ("
        "  STUDENT_ID INTEGER PRIMARY KEY,"
        "  FNAME TEXT NOT NULL,"
        "  LNAME TEXT NOT NULL,"
        "  CLASSIFICATION TEXT,"  
        "  SECTION TEXT NOT NULL "
        "    CHECK (SECTION IN ('WOODWIND','BRASS','PERCUSSION','AUXILIARY','DM')),"
        "  SHIRT_SIZE TEXT,"      
        "  SHOE_SIZE TEXT"        
        ");"
    );

    // COMPLIANCE table
    execSQL(
        "CREATE TABLE IF NOT EXISTS COMPLIANCE ("
        "  STUDENT_ID INTEGER PRIMARY KEY,"
        "  CREDIT_HOURS INTEGER NOT NULL DEFAULT 0 CHECK (CREDIT_HOURS >= 0),"
        "  GPA REAL NOT NULL DEFAULT 0.0,"
        "  DUES_PAID INTEGER NOT NULL DEFAULT 0 CHECK (DUES_PAID IN (0,1)),"
        "  LAST_VERIFIED_DATE TEXT,"
        "  FOREIGN KEY (STUDENT_ID) REFERENCES STUDENTS(STUDENT_ID) ON DELETE CASCADE"
        ");"
    );

    
    if (!columnExists("STUDENTS", "SHIRT_SIZE")) 
        execSQL("ALTER TABLE STUDENTS ADD COLUMN SHIRT_SIZE TEXT;");
    if (!columnExists("STUDENTS", "SHOE_SIZE")) 
        execSQL("ALTER TABLE STUDENTS ADD COLUMN SHOE_SIZE TEXT;");
    
    if (!columnExists("UNIFORMS", "COAT_SIZE")) {
        execSQL("DROP TABLE IF EXISTS UNIFORMS_OLD;");
        execSQL("ALTER TABLE UNIFORMS RENAME TO UNIFORMS_OLD;");
        
        execSQL(
            "CREATE TABLE UNIFORMS ("
            "  UNIFORM_ID INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  COAT_SIZE TEXT,"        
            "  PANT_SIZE TEXT,"       
            "  COAT_NUMBER TEXT,"      
            "  PANT_NUMBER TEXT,"      
            "  CONDITION_NOTES TEXT,"
            "  CHECKED_OUT_TO INTEGER UNIQUE,"
            "  CHECKED_OUT_DATE TEXT,"
            "  FOREIGN KEY (CHECKED_OUT_TO) REFERENCES STUDENTS(STUDENT_ID)"
            ");"
        );
        
        execSQL("INSERT INTO UNIFORMS (UNIFORM_ID, CONDITION_NOTES, CHECKED_OUT_TO, CHECKED_OUT_DATE) "
                "SELECT UNIFORM_ID, CONDITION_NOTES, CHECKED_OUT_TO, CHECKED_OUT_DATE "
                "FROM UNIFORMS_OLD;");
    }

    execSQL(
        "CREATE TABLE IF NOT EXISTS INSTRUMENT_TYPES ("
        "  TYPE_ID INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  TYPE_NAME TEXT UNIQUE NOT NULL,"
        "  SECTION TEXT NOT NULL CHECK (SECTION IN ('WOODWIND','BRASS','PERCUSSION','AUXILIARY','DM'))"
        ");"
    );

    execSQL(
        "CREATE TABLE IF NOT EXISTS INSTRUMENTS ("
        "  INSTRUMENT_ID INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  TYPE_ID INTEGER NOT NULL,"
        "  SERIAL TEXT UNIQUE,"
        "  CONDITION_NOTES TEXT,"
        "  CHECKED_OUT_TO INTEGER UNIQUE,"
        "  CHECKED_OUT_DATE TEXT,"
        "  FOREIGN KEY (TYPE_ID) REFERENCES INSTRUMENT_TYPES(TYPE_ID),"
        "  FOREIGN KEY (CHECKED_OUT_TO) REFERENCES STUDENTS(STUDENT_ID)"
        ");"
    );

    execSQL(
        "CREATE TABLE IF NOT EXISTS SHAKOS ("
        "  SHAKO_ID INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  SIZE TEXT,"
        "  CONDITION_NOTES TEXT,"
        "  CHECKED_OUT_TO INTEGER UNIQUE,"
        "  CHECKED_OUT_DATE TEXT,"
        "  FOREIGN KEY (CHECKED_OUT_TO) REFERENCES STUDENTS(STUDENT_ID)"
        ");"
    );

    execSQL(
        "CREATE TABLE IF NOT EXISTS SECTION_LEADERS ("
        "  SECTION TEXT PRIMARY KEY CHECK (SECTION IN ('WOODWIND','BRASS','PERCUSSION','AUXILIARY','DM')),"
        "  LEADER_STUDENT_ID INTEGER NOT NULL,"
        "  FOREIGN KEY (LEADER_STUDENT_ID) REFERENCES STUDENTS(STUDENT_ID)"
        ");"
    );

    execSQL(
        "INSERT OR IGNORE INTO INSTRUMENT_TYPES (TYPE_NAME, SECTION) VALUES "
        "('PICCOLO','WOODWIND'),"
        "('CLARINET','WOODWIND'),"
        "('SAXOPHONE','WOODWIND'),"
        "('TRUMPET','BRASS'),"
        "('TROMBONE','BRASS'),"
        "('SOUSAPHONE','BRASS'),"
        "('MELLOPHONE','BRASS'),"
        "('PERCUSSION','PERCUSSION'),"
        "('COLOR_GUARD','AUXILIARY');"
    );
}

static void studentsMenu();
static void instrumentsMenu();
static void uniformsMenu();
static void shakosMenu();
static void complianceMenu();

// Students
static void addStudent();
static void viewAllStudents();
static void findStudentById();
static void setSectionLeader();

// Instruments
static void checkoutInstrument();
static void returnInstrument();
static void viewInstrumentAssignments();
static void addInstrumentToInventory();

// Uniforms
static void checkoutUniform();
static void returnUniform();
static void viewUniformAssignments();

// Shakos
static void checkoutShako();
static void returnShako();
static void viewShakoAssignments();

// Compliance
static void updateStudentCompliance();
static void showEligibilityReport();

// ---------- Main ----------
int main() {
    if (sqlite3_open("band.db", &db) != SQLITE_OK) {
        cout << "Can't open database: " << sqlite3_errmsg(db) << "\n";
        return EXIT_FAILURE;
    }

    ensureTables();

    while (true) {
        cout << "\n========================================\n";
        cout << "         THE MARCHING DATABASE\n";
        cout << "========================================\n";
        cout << "[1] Students\n";
        cout << "[2] Instruments\n";
        cout << "[3] Uniforms\n";
        cout << "[4] Shakos\n";
        cout << "[5] Compliance Reports\n";
        cout << "[6] Exit\n";

        int choice = readIntInRange("\nChoice: ", 1, 6);

        if (choice == 1) studentsMenu();
        else if (choice == 2) instrumentsMenu();
        else if (choice == 3) uniformsMenu();
        else if (choice == 4) shakosMenu();
        else if (choice == 5) complianceMenu();
        else {
            sqlite3_close(db);
            cout << "Goodbye!\n";
            return EXIT_SUCCESS;
        }
    }
}

// ---------- Menus ----------
static void studentsMenu() {
    while (true) {
        cout << "\n----------- STUDENTS -----------\n";
        cout << "[1] Add student\n";
        cout << "[2] View all students\n";
        cout << "[3] Find student by ID\n";
        cout << "[4] Assign section leader\n";
        cout << "[5] Back\n";

        int choice = readIntInRange("Choice: ", 1, 5);

        switch (choice) {
            case 1: addStudent(); break;
            case 2: viewAllStudents(); break;
            case 3: findStudentById(); break;
            case 4: setSectionLeader(); break;
            case 5: return;
        }
    }
}

static void instrumentsMenu() {
    while (true) {
        cout << "\n---------- INSTRUMENTS ----------\n";
        cout << "[1] Check out instrument\n";
        cout << "[2] Return instrument\n";
        cout << "[3] View instrument assignments\n";
        cout << "[4] Add instrument to inventory\n";
        cout << "[5] Back\n";

        int choice = readIntInRange("Choice: ", 1, 5);

        if (choice == 1) checkoutInstrument();
        else if (choice == 2) returnInstrument();
        else if (choice == 3) viewInstrumentAssignments();
        else if (choice == 4) addInstrumentToInventory();
        else return;
    }
}

static void uniformsMenu() {
    while (true) {
        cout << "\n----------- UNIFORMS -----------\n";
        cout << "[1] Check out uniform\n";
        cout << "[2] Return uniform\n";
        cout << "[3] View uniform assignments\n";
        cout << "[4] Back\n";

        int choice = readIntInRange("Choice: ", 1, 4);

        if (choice == 1) checkoutUniform();
        else if (choice == 2) returnUniform();
        else if (choice == 3) viewUniformAssignments();
        else return;
    }
}

static void shakosMenu() {
    while (true) {
        cout << "\n------------ SHAKOS ------------\n";
        cout << "[1] Check out shako\n";
        cout << "[2] Return shako\n";
        cout << "[3] View shako assignments\n";
        cout << "[4] Back\n";

        int choice = readIntInRange("Choice: ", 1, 4);

        if (choice == 1) checkoutShako();
        else if (choice == 2) returnShako();
        else if (choice == 3) viewShakoAssignments();
        else return;
    }
}

static void complianceMenu() {
    while (true) {
        cout << "\n------ COMPLIANCE REPORTS ------\n";
        cout << "[1] Show eligibility report\n";
        cout << "[2] Update student compliance\n";
        cout << "[3] Back\n";

        int choice = readIntInRange("Choice: ", 1, 3);

        if (choice == 1) showEligibilityReport();
        else if (choice == 2) updateStudentCompliance();
        else return;
    }
}

// ---------- STUDENTS ----------
static void addStudent() {
    int id;
    string fname, lname, classification, section, shirtSize, shoeSize;

    cout << "\nStudent ID (number): ";
    cin >> id;
    clearInputLine();

    cout << "First name: ";
    getline(cin, fname);
    cout << "Last name: ";
    getline(cin, lname);

    cout << "Class (Freshman/Sophomore/Junior/Senior): "; 
    getline(cin, classification);
    classification = trim(classification);

    section = readSectionValidated("Section (WOODWIND/BRASS/PERCUSSION/AUXILIARY/DM): ");

    cout << "Shirt size (optional, XS/S/M/L/XL/XXL): ";
    getline(cin, shirtSize);
    shirtSize = trim(shirtSize);
    
    cout << "Shoe size (optional, numeric): ";
    getline(cin, shoeSize);
    shoeSize = trim(shoeSize);

    const char* sql =
        "INSERT INTO STUDENTS (STUDENT_ID, FNAME, LNAME, CLASSIFICATION, SECTION, SHIRT_SIZE, SHOE_SIZE) "
        "VALUES (?, ?, ?, ?, ?, ?, ?);";

    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
        return;
    }

    sqlite3_bind_int(stmt, 1, id);
    sqlite3_bind_text(stmt, 2, fname.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 3, lname.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 4, classification.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 5, section.c_str(), -1, SQLITE_TRANSIENT);
    
    if (shirtSize.empty()) 
        sqlite3_bind_null(stmt, 6);
    else 
        sqlite3_bind_text(stmt, 6, shirtSize.c_str(), -1, SQLITE_TRANSIENT);
        
    if (shoeSize.empty()) 
        sqlite3_bind_null(stmt, 7);
    else 
        sqlite3_bind_text(stmt, 7, shoeSize.c_str(), -1, SQLITE_TRANSIENT);

    if (sqlite3_step(stmt) != SQLITE_DONE) {
        cout << "Insert failed: " << sqlite3_errmsg(db) << "\n";
        sqlite3_finalize(stmt);
        return;
    }
    sqlite3_finalize(stmt);

    const char* csql =
        "INSERT OR IGNORE INTO COMPLIANCE "
        "(STUDENT_ID, CREDIT_HOURS, GPA, DUES_PAID, LAST_VERIFIED_DATE) "
        "VALUES (?, 0, 0.0, 0, date('now'));";

    sqlite3_stmt* cstmt = nullptr;
    if (sqlite3_prepare_v2(db, csql, -1, &cstmt, nullptr) == SQLITE_OK) {
        sqlite3_bind_int(cstmt, 1, id);
        sqlite3_step(cstmt);
        sqlite3_finalize(cstmt);
    }

    cout << "Student added.\n";
}

static void viewAllStudents() {
    const char* sql =
        "SELECT s.STUDENT_ID, s.FNAME, s.LNAME, s.CLASSIFICATION, s.SECTION, "
        "       COALESCE(s.SHIRT_SIZE,''), COALESCE(s.SHOE_SIZE,''), "
        "       COALESCE(c.CREDIT_HOURS,0), COALESCE(c.GPA,0.0), COALESCE(c.DUES_PAID,0), "
        "       (COALESCE(c.CREDIT_HOURS,0) >= 12 AND COALESCE(c.GPA,0.0) >= 3.0 AND COALESCE(c.DUES_PAID,0)=1) AS ELIGIBLE "
        "FROM STUDENTS s "
        "LEFT JOIN COMPLIANCE c ON c.STUDENT_ID=s.STUDENT_ID "
        "ORDER BY s.SECTION, s.LNAME, s.FNAME;";

    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
        return;
    }

    cout << "\nID   NAME                 CLASS          SECTION     SHIRT SHOE  HRS  GPA   DUES  ELIG\n";
    cout << "----------------------------------------------------------------------------------------\n";
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        int id = sqlite3_column_int(stmt, 0);
        string name = string(colText(stmt, 1)) + " " + colText(stmt, 2);
        string classif = colText(stmt, 3);

        int hrs = sqlite3_column_int(stmt, 7);
        double gpa = sqlite3_column_double(stmt, 8);
        int dues = sqlite3_column_int(stmt, 9);
        int elig = sqlite3_column_int(stmt, 10);

        cout << left
             << setw(5)  << id
             << setw(21) << name
             << setw(15) << classif
             << setw(12) << colText(stmt, 4)  
             << setw(6)  << colText(stmt, 5)  
             << setw(6)  << colText(stmt, 6)  
             << setw(5)  << hrs
             << setw(6)  << fixed << setprecision(2) << gpa
             << setw(6)  << (dues ? "YES" : "NO")
             << (elig ? "YES" : "NO")
             << "\n";
    }

    sqlite3_finalize(stmt);
}

static void findStudentById() {
    int id;
    cout << "\nStudent ID: ";
    cin >> id;

    const char* sql =
        "SELECT s.STUDENT_ID, s.FNAME, s.LNAME, s.CLASSIFICATION, s.SECTION, "
        "       COALESCE(s.SHIRT_SIZE,''), COALESCE(s.SHOE_SIZE,''), "
        "       COALESCE(c.CREDIT_HOURS,0), COALESCE(c.GPA,0.0), COALESCE(c.DUES_PAID,0), "
        "       COALESCE(c.LAST_VERIFIED_DATE,'') "
        "FROM STUDENTS s "
        "LEFT JOIN COMPLIANCE c ON c.STUDENT_ID=s.STUDENT_ID "
        "WHERE s.STUDENT_ID=?;";

    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
        return;
    }

    sqlite3_bind_int(stmt, 1, id);

    if (sqlite3_step(stmt) == SQLITE_ROW) {
        int hrs = sqlite3_column_int(stmt, 7);
        double gpa = sqlite3_column_double(stmt, 8);
        int dues = sqlite3_column_int(stmt, 9);
        bool eligible = (hrs >= 12 && gpa >= 3.0 && dues == 1);

        cout << "\n--- STUDENT PROFILE ---\n";
        cout << "ID: " << sqlite3_column_int(stmt, 0) << "\n";
        cout << "Name: " << colText(stmt, 1) << " " << colText(stmt, 2) << "\n";
        cout << "Class: " << colText(stmt, 3) << "\n";  
        cout << "Section: " << colText(stmt, 4) << "\n";
        cout << "Shirt Size: " << colText(stmt, 5) << "\n";
        cout << "Shoe Size: " << colText(stmt, 6) << "\n";
        cout << "Credit Hours: " << hrs << "\n";
        cout << "GPA: " << fixed << setprecision(2) << gpa << "\n";
        cout << "Dues Paid: " << (dues ? "YES" : "NO") << "\n";
        cout << "Eligible to march: " << (eligible ? "YES" : "NO") << "\n";
        cout << "Last Verified: " << colText(stmt, 10) << "\n";
    } else {
        cout << "No student found with that ID.\n";
    }

    sqlite3_finalize(stmt);
}

static void setSectionLeader() {
    clearInputLine();
    string section = readSectionValidated("\nSection (WOODWIND/BRASS/PERCUSSION/AUXILIARY/DM): ");

    cout << "Leader student ID: ";
    int leaderId;
    cin >> leaderId;

    if (!studentExists(leaderId)) {
        cout << "This student ID doesn'texist. Please add the student first.\n";
        return;
    }

    const char* sql =
        "INSERT INTO SECTION_LEADERS (SECTION, LEADER_STUDENT_ID) "
        "VALUES (?, ?) "
        "ON CONFLICT(SECTION) DO UPDATE SET LEADER_STUDENT_ID=excluded.LEADER_STUDENT_ID;";

    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
        return;
    }

    sqlite3_bind_text(stmt, 1, section.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_int(stmt, 2, leaderId);

    if (sqlite3_step(stmt) != SQLITE_DONE) {
        cout << "Set leader failed: " << sqlite3_errmsg(db) << "\n";
    } else {
        cout << "Section leader saved.\n";
    }

    sqlite3_finalize(stmt);
}

// ---------- INSTRUMENTS ----------
static void addInstrumentToInventory() {
    cout << "\nInstrument Types:\n";
    const char* listSql = "SELECT TYPE_ID, TYPE_NAME, SECTION FROM INSTRUMENT_TYPES ORDER BY SECTION, TYPE_NAME;";
    sqlite3_stmt* listStmt = nullptr;

    if (sqlite3_prepare_v2(db, listSql, -1, &listStmt, nullptr) != SQLITE_OK) {
        cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
        return;
    }
    while (sqlite3_step(listStmt) == SQLITE_ROW) {
        cout << sqlite3_column_int(listStmt, 0) << ". "
             << colText(listStmt, 1) << " (" << colText(listStmt, 2) << ")\n";
    }
    sqlite3_finalize(listStmt);

    int typeId;
    cout << "\nChoose TYPE_ID: ";
    cin >> typeId;
    clearInputLine();

    string serial, notes;
    cout << "Serial (optional): ";
    getline(cin, serial);
    cout << "Condition notes (optional): ";
    getline(cin, notes);

    const char* sql =
        "INSERT INTO INSTRUMENTS (TYPE_ID, SERIAL, CONDITION_NOTES) "
        "VALUES (?, ?, ?);";

    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
        return;
    }

    sqlite3_bind_int(stmt, 1, typeId);
    if (serial.empty()) sqlite3_bind_null(stmt, 2);
    else sqlite3_bind_text(stmt, 2, serial.c_str(), -1, SQLITE_TRANSIENT);

    if (notes.empty()) sqlite3_bind_null(stmt, 3);
    else sqlite3_bind_text(stmt, 3, notes.c_str(), -1, SQLITE_TRANSIENT);

    if (sqlite3_step(stmt) != SQLITE_DONE) {
        cout << "Add failed: " << sqlite3_errmsg(db) << "\n";
    } else {
        cout << "Instrument added to inventory.\n";
    }

    sqlite3_finalize(stmt);
}

static void checkoutInstrument() {
    int studentId;
    cout << "\nStudent ID: ";
    cin >> studentId;
    clearInputLine();

    string studentSection;
    if (!getStudentSection(studentId, studentSection)) {
        cout << "This student ID does not exist. Please add the student first.\n";
        return;
    }

    cout << "\nFilter available instruments by student's SECTION (" << studentSection << ")?\n";
    int filter = readIntInRange("[1] Yes  [2] No\nChoice: ", 1, 2);

    const char* sqlFiltered =
        "SELECT i.INSTRUMENT_ID, t.TYPE_NAME, COALESCE(i.SERIAL,''), COALESCE(i.CONDITION_NOTES,'') "
        "FROM INSTRUMENTS i "
        "JOIN INSTRUMENT_TYPES t ON t.TYPE_ID=i.TYPE_ID "
        "WHERE i.CHECKED_OUT_TO IS NULL AND t.SECTION=? "
        "ORDER BY t.TYPE_NAME, i.INSTRUMENT_ID;";

    const char* sqlAll =
        "SELECT i.INSTRUMENT_ID, t.TYPE_NAME, COALESCE(i.SERIAL,''), COALESCE(i.CONDITION_NOTES,'') "
        "FROM INSTRUMENTS i "
        "JOIN INSTRUMENT_TYPES t ON t.TYPE_ID=i.TYPE_ID "
        "WHERE i.CHECKED_OUT_TO IS NULL "
        "ORDER BY t.SECTION, t.TYPE_NAME, i.INSTRUMENT_ID;";

    sqlite3_stmt* stmt = nullptr;

    if (filter == 1) {
        if (sqlite3_prepare_v2(db, sqlFiltered, -1, &stmt, nullptr) != SQLITE_OK) {
            cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
            return;
        }
        sqlite3_bind_text(stmt, 1, studentSection.c_str(), -1, SQLITE_TRANSIENT);
    } else {
        if (sqlite3_prepare_v2(db, sqlAll, -1, &stmt, nullptr) != SQLITE_OK) {
            cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
            return;
        }
    }

    cout << "\nAvailable Instruments";
    if (filter == 1) cout << " (SECTION: " << studentSection << ")";
    cout << ":\n";

    cout << "ID   TYPE         SERIAL        CONDITION NOTES\n";
    cout << "------------------------------------------------\n";

    bool any = false;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        any = true;
        cout << left
             << setw(5) << sqlite3_column_int(stmt, 0)
             << setw(13) << colText(stmt, 1)
             << setw(13) << colText(stmt, 2)
             << colText(stmt, 3)
             << "\n";
    }
    sqlite3_finalize(stmt);

    if (!any) {
        cout << "No instruments available for that view.\n";
        return;
    }

    cout << "\nEnter INSTRUMENT_ID to check out: ";
    int instrumentId;
    cin >> instrumentId;

    const char* upd =
        "UPDATE INSTRUMENTS "
        "SET CHECKED_OUT_TO=?, CHECKED_OUT_DATE=date('now') "
        "WHERE INSTRUMENT_ID=? AND CHECKED_OUT_TO IS NULL;";

    sqlite3_stmt* updStmt = nullptr;
    if (sqlite3_prepare_v2(db, upd, -1, &updStmt, nullptr) != SQLITE_OK) {
        cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
        return;
    }

    sqlite3_bind_int(updStmt, 1, studentId);
    sqlite3_bind_int(updStmt, 2, instrumentId);

    if (sqlite3_step(updStmt) != SQLITE_DONE) {
        cout << "Checkout failed: " << sqlite3_errmsg(db) << "\n";
        cout << "Note: student can only hold ONE instrument at a time.\n";
    } else {
        int changes = sqlite3_changes(db);
        if (!changes) cout << "Invaild. Instrument already checked out OR that ID doesn't exist!\n";
        else cout << "Instrument checked out.\n";
    }

    sqlite3_finalize(updStmt);
}

static void returnInstrument() {
    const char* sql =
        "SELECT i.INSTRUMENT_ID, t.TYPE_NAME, COALESCE(i.SERIAL,''), i.CHECKED_OUT_TO, COALESCE(i.CHECKED_OUT_DATE,'') "
        "FROM INSTRUMENTS i "
        "JOIN INSTRUMENT_TYPES t ON t.TYPE_ID=i.TYPE_ID "
        "WHERE i.CHECKED_OUT_TO IS NOT NULL "
        "ORDER BY i.INSTRUMENT_ID;";

    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
        return;
    }

    cout << "\nChecked-Out Instruments:\n";
    cout << "ID   TYPE         SERIAL        STUDENT   DATE\n";
    cout << "------------------------------------------------\n";

    bool any = false;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        any = true;
        cout << left
             << setw(5) << sqlite3_column_int(stmt, 0)
             << setw(13) << colText(stmt, 1)
             << setw(13) << colText(stmt, 2)
             << setw(10) << sqlite3_column_int(stmt, 3)
             << colText(stmt, 4)
             << "\n";
    }
    sqlite3_finalize(stmt);

    if (!any) {
        cout << "None.\n";
        return;
    }

    cout << "\nEnter INSTRUMENT_ID to return: ";
    int instrumentId;
    cin >> instrumentId;

    const char* upd =
        "UPDATE INSTRUMENTS "
        "SET CHECKED_OUT_TO=NULL, CHECKED_OUT_DATE=NULL "
        "WHERE INSTRUMENT_ID=?;";

       sqlite3_stmt* updStmt = nullptr;
    if (sqlite3_prepare_v2(db, upd, -1, &updStmt, nullptr) != SQLITE_OK) {
        cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
        return;
    }

    sqlite3_bind_int(updStmt, 1, instrumentId);

    if (sqlite3_step(updStmt) != SQLITE_DONE) {
        cout << "Return failed: " << sqlite3_errmsg(db) << "\n";
    } else {
        cout << (sqlite3_changes(db) ? "Instrument returned.\n" : "No instrument with that ID.\n");
    }

    sqlite3_finalize(updStmt);
}

static void viewInstrumentAssignments() {
    const char* sql =
        "SELECT i.INSTRUMENT_ID, t.TYPE_NAME, COALESCE(i.SERIAL,''), "
        "       COALESCE(i.CHECKED_OUT_TO,0), COALESCE(i.CHECKED_OUT_DATE,''), "
        "       COALESCE(i.CONDITION_NOTES,'') "
        "FROM INSTRUMENTS i "
        "JOIN INSTRUMENT_TYPES t ON t.TYPE_ID=i.TYPE_ID "
        "ORDER BY (i.CHECKED_OUT_TO IS NULL) DESC, t.SECTION, t.TYPE_NAME, i.INSTRUMENT_ID;";

    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
        return;
    }

    cout << "\nINSTRUMENT ASSIGNMENTS\n";
    cout << "ID   TYPE         SERIAL        STUDENT   DATE       CONDITION NOTES\n";
    cout << "---------------------------------------------------------------------\n";

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        cout << left
             << setw(5) << sqlite3_column_int(stmt, 0)
             << setw(13) << colText(stmt, 1)
             << setw(13) << colText(stmt, 2)
             << setw(10) << sqlite3_column_int(stmt, 3)
             << setw(12) << colText(stmt, 4)
             << colText(stmt, 5)
             << "\n";
    }

    sqlite3_finalize(stmt);
}

// ---------- UNIFORMS ----------
static void checkoutUniform() {
    int studentId;
    cout << "\nStudent ID: ";
    cin >> studentId;
    clearInputLine();

    if (!studentExists(studentId)) {
        cout << "This student ID doesn't exist. Please add the student first!\n";
        return;
    }

    string coatSize, pantSize, coatNumber, pantNumber, notes;
    cout << "Coat size (optional): ";
    getline(cin, coatSize);
    cout << "Pant size (optional): ";
    getline(cin, pantSize);
    cout << "Coat number (optional): ";
    getline(cin, coatNumber);
    cout << "Pant number (optional): ";
    getline(cin, pantNumber);
    cout << "Condition notes (optional): ";
    getline(cin, notes);

    const char* sql =
        "INSERT INTO UNIFORMS (COAT_SIZE, PANT_SIZE, COAT_NUMBER, PANT_NUMBER, CONDITION_NOTES, CHECKED_OUT_TO, CHECKED_OUT_DATE) "
        "VALUES (?, ?, ?, ?, ?, ?, date('now'));";

    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
        return;
    }

    int col = 1;
    if (coatSize.empty()) sqlite3_bind_null(stmt, col++);
    else sqlite3_bind_text(stmt, col++, coatSize.c_str(), -1, SQLITE_TRANSIENT);
    
    if (pantSize.empty()) sqlite3_bind_null(stmt, col++);
    else sqlite3_bind_text(stmt, col++, pantSize.c_str(), -1, SQLITE_TRANSIENT);
    
    if (coatNumber.empty()) sqlite3_bind_null(stmt, col++);
    else sqlite3_bind_text(stmt, col++, coatNumber.c_str(), -1, SQLITE_TRANSIENT);
    
    if (pantNumber.empty()) sqlite3_bind_null(stmt, col++);
    else sqlite3_bind_text(stmt, col++, pantNumber.c_str(), -1, SQLITE_TRANSIENT);
    
    if (notes.empty()) sqlite3_bind_null(stmt, col++);
    else sqlite3_bind_text(stmt, col++, notes.c_str(), -1, SQLITE_TRANSIENT);
    
    sqlite3_bind_int(stmt, col++, studentId);

    if (sqlite3_step(stmt) != SQLITE_DONE) {
        cout << "Checkout failed: " << sqlite3_errmsg(db) << "\n";
        cout << "Note: a student can only have ONE uniform at a time.\n";
    } else {
        cout << "Uniform checked out.\n";
    }

    sqlite3_finalize(stmt);
}

static void returnUniform() {
    const char* sql =
        "SELECT UNIFORM_ID, COALESCE(COAT_SIZE,''), COALESCE(PANT_SIZE,''), "
        "       COALESCE(COAT_NUMBER,''), COALESCE(PANT_NUMBER,''), "
        "       CHECKED_OUT_TO, COALESCE(CHECKED_OUT_DATE,'') "
        "FROM UNIFORMS WHERE CHECKED_OUT_TO IS NOT NULL ORDER BY UNIFORM_ID;";

    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
        return;
    }

    cout << "\nChecked-Out Uniforms:\n";
    cout << "ID   COAT  PANT  C#   P#   STUDENT   DATE\n";
    cout << "-----------------------------------------\n";

    bool any = false;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        any = true;
        cout << left
             << setw(5) << sqlite3_column_int(stmt, 0)
             << setw(6) << colText(stmt, 1)
             << setw(6) << colText(stmt, 2)
             << setw(5) << colText(stmt, 3)
             << setw(5) << colText(stmt, 4)
             << setw(10) << sqlite3_column_int(stmt, 5)
             << colText(stmt, 6)
             << "\n";
    }
    sqlite3_finalize(stmt);

    if (!any) {
        cout << "None.\n";
        return;
    }

    cout << "\nEnter UNIFORM_ID to return: ";
    int uniformId;
    cin >> uniformId;

    const char* upd =
        "UPDATE UNIFORMS SET CHECKED_OUT_TO=NULL, CHECKED_OUT_DATE=NULL WHERE UNIFORM_ID=?;";

    sqlite3_stmt* updStmt = nullptr;
    if (sqlite3_prepare_v2(db, upd, -1, &updStmt, nullptr) != SQLITE_OK) {
        cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
        return;
    }

    sqlite3_bind_int(updStmt, 1, uniformId);

    if (sqlite3_step(updStmt) != SQLITE_DONE) {
        cout << "Return failed: " << sqlite3_errmsg(db) << "\n";
    } else {
        cout << (sqlite3_changes(db) ? "Uniform returned.\n" : "No uniform with that ID.\n");
    }

    sqlite3_finalize(updStmt);
}

static void viewUniformAssignments() {
    const char* sql =
        "SELECT UNIFORM_ID, COALESCE(COAT_SIZE,''), COALESCE(PANT_SIZE,''), "
        "       COALESCE(COAT_NUMBER,''), COALESCE(PANT_NUMBER,''), "
        "       COALESCE(CONDITION_NOTES,''), "
        "       COALESCE(CHECKED_OUT_TO,0), COALESCE(CHECKED_OUT_DATE,'') "
        "FROM UNIFORMS ORDER BY (CHECKED_OUT_TO IS NULL) DESC, UNIFORM_ID;";

    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
        return;
    }

    cout << "\nUNIFORM ASSIGNMENTS\n";
    cout << "ID   COAT  PANT  C#   P#   STUDENT   DATE       CONDITION NOTES\n";
    cout << "----------------------------------------------------------------\n";

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        cout << left
             << setw(5) << sqlite3_column_int(stmt, 0)
             << setw(6) << colText(stmt, 1)
             << setw(6) << colText(stmt, 2)
             << setw(5) << colText(stmt, 3)
             << setw(5) << colText(stmt, 4)
             << setw(10) << sqlite3_column_int(stmt, 6)
             << setw(12) << colText(stmt, 7)
             << colText(stmt, 5)
             << "\n";
    }

    sqlite3_finalize(stmt);
}

// ---------- SHAKOS ----------
static void checkoutShako() {
    int studentId;
    cout << "\nStudent ID: ";
    cin >> studentId;
    clearInputLine();

    if (!studentExists(studentId)) {
        cout << "This student ID doesn't exist. Please add the student first!\n";
        return;
    }

    string size, notes;
    cout << "Shako size (optional): ";
    getline(cin, size);
    cout << "Condition notes (optional): ";
    getline(cin, notes);

    const char* sql =
        "INSERT INTO SHAKOS (SIZE, CONDITION_NOTES, CHECKED_OUT_TO, CHECKED_OUT_DATE) "
        "VALUES (?, ?, ?, date('now'));";

    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
        return;
    }

    if (size.empty()) sqlite3_bind_null(stmt, 1);
    else sqlite3_bind_text(stmt, 1, size.c_str(), -1, SQLITE_TRANSIENT);

    if (notes.empty()) sqlite3_bind_null(stmt, 2);
    else sqlite3_bind_text(stmt, 2, notes.c_str(), -1, SQLITE_TRANSIENT);

    sqlite3_bind_int(stmt, 3, studentId);

    if (sqlite3_step(stmt) != SQLITE_DONE) {
        cout << "Checkout failed: " << sqlite3_errmsg(db) << "\n";
        cout << "Note: a student may only hold ONE shako at a time.\n";
    } else {
        cout << "Shako checked out.\n";
    }

    sqlite3_finalize(stmt);
}

static void returnShako() {
    const char* sql =
        "SELECT SHAKO_ID, COALESCE(SIZE,''), CHECKED_OUT_TO, COALESCE(CHECKED_OUT_DATE,''), "
        "       COALESCE(CONDITION_NOTES,'') "
        "FROM SHAKOS WHERE CHECKED_OUT_TO IS NOT NULL ORDER BY SHAKO_ID;";

    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
        return;
    }

    cout << "\nChecked-Out Shakos:\n";
    cout << "ID   SIZE         STUDENT   DATE       CONDITION NOTES\n";
    cout << "-------------------------------------------------------\n";

    bool any = false;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        any = true;
        cout << left
             << setw(5) << sqlite3_column_int(stmt, 0)
             << setw(13) << colText(stmt, 1)
             << setw(10) << sqlite3_column_int(stmt, 2)
             << setw(12) << colText(stmt, 3)
             << colText(stmt, 4)
             << "\n";
    }
    sqlite3_finalize(stmt);

    if (!any) {
        cout << "None.\n";
        return;
    }

    cout << "\nEnter SHAKO_ID to return: ";
    int shakoId;
    cin >> shakoId;

    const char* upd =
        "UPDATE SHAKOS SET CHECKED_OUT_TO=NULL, CHECKED_OUT_DATE=NULL WHERE SHAKO_ID=?;";

    sqlite3_stmt* updStmt = nullptr;
    if (sqlite3_prepare_v2(db, upd, -1, &updStmt, nullptr) != SQLITE_OK) {
        cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
        return;
    }

    sqlite3_bind_int(updStmt, 1, shakoId);

    if (sqlite3_step(updStmt) != SQLITE_DONE) {
        cout << "Return failed: " << sqlite3_errmsg(db) << "\n";
    } else {
        cout << (sqlite3_changes(db) ? "Shako returned.\n" : "No shako with that ID.\n");
    }

    sqlite3_finalize(updStmt);
}

static void viewShakoAssignments() {
    const char* sql =
        "SELECT SHAKO_ID, COALESCE(SIZE,''), COALESCE(CHECKED_OUT_TO,0), "
        "       COALESCE(CHECKED_OUT_DATE,''), COALESCE(CONDITION_NOTES,'') "
        "FROM SHAKOS ORDER BY (CHECKED_OUT_TO IS NULL) DESC, SHAKO_ID;";

    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
        return;
    }

    cout << "\nSHAKO ASSIGNMENTS\n";
    cout << "ID   SIZE         STUDENT   DATE       CONDITION NOTES\n";
    cout << "-------------------------------------------------------\n";

    bool any = false;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        any = true;
        cout << left
             << setw(5) << sqlite3_column_int(stmt, 0)
             << setw(13) << colText(stmt, 1)
             << setw(10) << sqlite3_column_int(stmt, 2)
             << setw(12) << colText(stmt, 3)
             << colText(stmt, 4)
             << "\n";
    }
    if (!any) cout << "(none)\n";

    sqlite3_finalize(stmt);
}

// ---------- COMPLIANCE ----------
static void updateStudentCompliance() {
    int id;
    cout << "\nStudent ID: ";
    cin >> id;
    clearInputLine();

    if (!studentExists(id)) {
        cout << "This student ID doesn't exist. Please add the student first!\n";
        return;
    }

    int hours = readIntInRange("Credit hours (0-30): ", 0, 30);
    double gpa = readDoubleInRange("GPA (0.00-4.00): ", 0.0, 4.0);
    int dues = readBool01("Dues paid? (1=yes, 0=no): ");

    const char* sql =
        "INSERT INTO COMPLIANCE (STUDENT_ID, CREDIT_HOURS, GPA, DUES_PAID, LAST_VERIFIED_DATE) "
        "VALUES (?, ?, ?, ?, date('now')) "
        "ON CONFLICT(STUDENT_ID) DO UPDATE SET "
        "CREDIT_HOURS=excluded.CREDIT_HOURS, "
        "GPA=excluded.GPA, "
        "DUES_PAID=excluded.DUES_PAID, "
        "LAST_VERIFIED_DATE=excluded.LAST_VERIFIED_DATE;";

    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
        return;
    }

    sqlite3_bind_int(stmt, 1, id);
    sqlite3_bind_int(stmt, 2, hours);
    sqlite3_bind_double(stmt, 3, gpa);
    sqlite3_bind_int(stmt, 4, dues);

    if (sqlite3_step(stmt) != SQLITE_DONE) {
        cout << "Update failed: " << sqlite3_errmsg(db) << "\n";
    } else {
        cout << "Compliance saved.\n";
    }

    sqlite3_finalize(stmt);
}

static void showEligibilityReport() {
    const char* sql =
        "SELECT s.STUDENT_ID, s.FNAME, s.LNAME, s.CLASSIFICATION, s.SECTION, "
        "       COALESCE(c.CREDIT_HOURS,0), COALESCE(c.GPA,0.0), COALESCE(c.DUES_PAID,0), "
        "       COALESCE(c.LAST_VERIFIED_DATE,''), "
        "       (COALESCE(c.CREDIT_HOURS,0) >= 12) AS OK_HRS, "
        "       (COALESCE(c.GPA,0.0) >= 3.0) AS OK_GPA, "
        "       (COALESCE(c.DUES_PAID,0) = 1) AS OK_DUES, "
        "       (COALESCE(c.CREDIT_HOURS,0) >= 12 AND COALESCE(c.GPA,0.0) >= 3.0 AND COALESCE(c.DUES_PAID,0)=1) AS ELIG "
        "FROM STUDENTS s "
        "LEFT JOIN COMPLIANCE c ON c.STUDENT_ID=s.STUDENT_ID "
        "ORDER BY ELIG ASC, s.SECTION, s.LNAME, s.FNAME;";

    sqlite3_stmt* stmt = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK) {
        cout << "SQL error: " << sqlite3_errmsg(db) << "\n";
        return;
    }

    cout << "\nELIGIBILITY REPORT (needs: >=12 hrs, >=3.0 GPA, dues paid)\n";
    cout << "ID   NAME                 CLASS      SECTION     HRS  GPA   DUES  OK_H OK_G OK_D ELIG  VERIFIED\n";
    cout << "-----------------------------------------------------------------------------------------------\n";

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        int id = sqlite3_column_int(stmt, 0);
        string name = string(colText(stmt, 1)) + " " + colText(stmt, 2);
        string classif = colText(stmt, 3);
        string sec = colText(stmt, 4);
        int hrs = sqlite3_column_int(stmt, 5);
        double gpa = sqlite3_column_double(stmt, 6);
        int dues = sqlite3_column_int(stmt, 7);
        string verified = colText(stmt, 8);

        int okH = sqlite3_column_int(stmt, 9);
        int okG = sqlite3_column_int(stmt, 10);
        int okD = sqlite3_column_int(stmt, 11);
        int elig = sqlite3_column_int(stmt, 12);

        cout << left
             << setw(6)  << id
             << setw(21) << name
             << setw(11) << classif
             << setw(12) << sec
             << setw(5)  << hrs
             << setw(6)  << fixed << setprecision(2) << gpa
             << setw(6)  << (dues ? "YES" : "NO")
             << setw(5)  << (okH ? "Y" : "N")
             << setw(5)  << (okG ? "Y" : "N")
             << setw(5)  << (okD ? "Y" : "N")
             << setw(6)  << (elig ? "YES" : "NO")
             << verified
             << "\n";
    }

    sqlite3_finalize(stmt);
}