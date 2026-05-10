export type Auth = {
  id: number;
  email: string;
  password: string;
  token: string;
  site: string;
  seller: Seller;
  area: string;
  cambridgeUser: string;
  user: string;
  menuItems: any[];
  teams: Auth[];
  zone: Zone;
};

export type Zone = {
  name: string;
  id: number;
};
export type MenuItem = {
  id: number;
  location: string;
  name: string;
  version: number;
  comments: string;
  auths: Auth;
  users: Auth;
};
export type Google = {
  id: number | string;
  file: File;
  name: string;
  contentType: string;
  url: string;
  data: { name: string; contentType: string; url: string }[];
};
export type Payment = {
  id: number;
  quantity: number;
  status: string;
  createdAt: Date;
  updatedAt: Date;
  cart: Cart;
  billingId: string;
  use: string;
  comments: string;
  billingStatus: string;
  cartProduct: CartProduct;
  student: Student;
  ref: string;
  method: string;
  paymentDate: Date;
  fileName: string;
  userComments: string;
  parent: Payment;
  payMethod: string;
  studentPayments: StudentPayment[];
};

export type StudentPayment = {
  payment: Payment; 
  paymentId: number;
  studentId: number;
  student: Student;
  amount: number;
  id: number;
};

export type Cart = {
  id: number;
  saleType: string;
  billingStatus: string;
  createdAt: Date;
  deletedAt: Date;
  sellerLeadId: number;
  sellerLead: SellerLead;
  generalDiscount: number;
  proration: number;
  subTotal: number;
  total: number;
  originId: number;
  origin: Cart;
  cost: number;
  updatedAt: number;
  bookCommission: number;
  examCommission: number;
  histories: History[];
  products: CartProduct[];
  cartBillings: CartBilling[];
  cartPayments: Payment[];
  cartProject: Project;
};

export type SellerLead = {
  id: number;
  promotionalStatus: string;
  businessStatus: string;
  leadId: number;
  lead: Lead;
  carts: Cart[];
  sellerId: number;
  seller: Seller;
  campaignId: number;
  deletedAt: Date;
};

export type CartBilling = {
  id: number;
  amount: number;
  comments: string;
  status: string;
  response: string;
  billId: string;
  billDate: string;
  leadBilling: LeadBilling;
  carts: Cart[];
};

export type LeadContact = {
  id: number;
  name: string;
  phoneNumber: string;
  areaCountry: string;
  emailAddress: string;
  position: string;
  lead: Lead;
  deletedAt: Date;
  contactLevel: Grade;
};
export type Lead = {
  id: number;
  name: string;
  globalState: string;
  zoneId: number;
  cct: number;
  support: string;
  site: string;
  type: string;
  nomenclature: string;
  cambridge_user: number;
  writingTest: string;
  corporation_id: number;
  alias: string;
  flow: string;
  campaign: string;
  schoolGrades: Array<SchoolGrades>;
  sellerLead: SellerLead;
  contacts: Array<LeadContact>;
  addresses: Array<LeadAddress>;
  billingDatums: Array<LeadBilling>;
  venue: Venue;
  leadProject: Project;
};
export type LeadBilling = {
  id: number;
  billingId: string;
  lead: Lead;
  type: string;
  method: string;
  student: Student;
  contact: LeadContact;
  address: LeadAddress;
};
export type LeadAddress = {
  id: number;
  street: string;
  extNum: string;
  intNum: string;
  colony: string;
  stateName: string;
  city: string;
  postalCode: string;
  corner1: string;
  corner2: string;
  comments: string;
  isFavorite: number;
  lead: Lead;
  addressLevel: Grade;
  lat: string;
  lng: string;
  deletedAt: Date;
};

export type SchoolGrades = {
  id: number;
  externalId: number;
  schoolGrade: Grade;
  grades: any;
  lead: Lead;
};

export type Grade = {
  id: number;
  name: string;
  description: string;
  cambridgeName: string;
  levels: Array<Level>;
};

export type Level = {
  id: number;
  name: string;
  shortName: string;
  schoolGrade: Grade;
};
export type Seller = {
  id: number;
  name: string;
  lastName: string;
  auth: Auth;
  admins: Auth[];
};

export type Product = {
  id: number;
  name: string;
  purchasePrice: number;
  salePrice: number;
  productType: string;
  isbn: string;
  edition: number;
  publishing: string;
  presentation: string;
  tab: string;
  userTarget: string;
  schoolLevel: string;
  criteria1: string;
  criteria2: string;
  criteria3: string;
  criteria4: string;
  stock: number;
  dateType: string;
  site: string;
  duration: number;
  duration2: number;
  saleUsdPrice: number;
  examId: number;
  exam: ExamCat;
  examCat: ExamCat;
  fixedCosts: ApplicationCost[];
};
export type CartProduct = {
  id: number;
  quantity: number;
  discount: number;
  cost: number;
  dueDate: Date;
  testDate: Date;
  createdAt: Date;
  cartId: number;
  cart: Cart;
  productId: number;
  product: Product;
  book: Product;
  gradeLevelId: number;
  gradeLevel: Level;
  bookGradeLevel: Level;
  taxes: number;
  subTotal: number;
  total: number;
  deliveryDate: Date;
  examId: number;
  exam: CartProduct;
  endDate: Date;
  scholarship: number;
  deletedAt: Date;
  closeDate: Date;
  asesorCloseDate: Date;
  comercialCloseDate: Date;
  financeCloseDate: Date;
  examsCloseDate: Date;
  books: CartProduct[];
  students: Student[];
  origin: CartProduct;
  reprogramations: CartProduct[];
};

export type ExamCat = {
  id: number;
  name: string;
  presentation: string;
  dateType: string;
  dates: Array<ExamDatesCat>;
  products: Array<Product>;
  duration: number;
  oralDuration: number;
  shortName: string;
  fixedCosts: ApplicationCost[];
  readingAndWriting: number;
  reading: number;
  writing: number;
  listening: number;
  speacking: number;
  break1: number;
  break2: number;
  break3: number;
};

export type ExamDatesCat = {
  id: number;
  testDate: Date;
  closeDate: Date;
  asesorCloseDate: Date;
  comercialCloseDate: Date;
  financeCloseDate: Date;
  examsCloseDate: Date;
  exam: ExamCat;
};

type FeedbackItem = {
  itemName: string;
  mark: string;
  feedback: string;
};

type ImprovementItem = {
  itemName: string;
  feedback: string;
};

type Resume = {
  content: string;
  overall: string;
};

export type Evaluation = {
  CFLR: string;
  marks: FeedbackItem[];
  improvements: ImprovementItem[];
  resume: Resume;
  level: string;
  model: string;
};

export type LeadMockCat = {
  id: number;
  name: string;
  title: string;
  content: string;
  type: "system" | "user";
  level: string;
  user: number;
};

export type LeadMock = {
  id: number;
  createdAt: Date;
  leadId: number;
  lead: Lead;
  auth_id: number;
  user: Auth;
  mocks: LeadMockCat[];
  candidates: LeadMockCandidate[];
  schoolGradeLevel: Level;
};

export type LeadMockCandidate = {
  id: number;
  createdAt: Date;
  updatedAt: Date;
  status: string;
  email: string;
  firstName: string;
  lastName: string;
  phone: string;
  level: string;
  leadMockId: number;
  leadMock: LeadMock;
  reportItems: LeadMockReport[];
};

export type LeadMockReport = {
  id: number;
  itemName: string;
  content: string;
  mark: string;
  type: string;
  candidate: LeadMockCandidate;
  leadMock: LeadMock;
};

export type History = {
  id: number;
  content: string;
  status: string;
  createdAt: Date;
  userId: number;
  user: Auth;
  cartId: number;
  cart: Cart;
  businessActionId: number;
  ieltsLeadId: number;
  ieltsLead: IeltsConfirmation;
  studentId: number;
  student: Student;
  variableCosts: ApplicationCost;
};

export type ApplicationCost = {
  id: number;
  name: string;
  amount: number;
  product: Product;
  cart: Cart;
  exam: ExamCat;
  site: string;
};
export type IeltsConfirmation = {
  id: number;
  status: string;
  comments: string;
  createdAt: Date;
  updatedAt: Date;
  user: Auth;
  cartProduct: CartProduct;
};
export type Student = {
  id: number;
  name: string;
  birthDate: string;
  cartProductId: number;
  cartProduct: CartProduct;
  email: string;
  gender: string;
  lastName: string;
  nationality: string;
  identityDocumentNumber: string;
  partCode: string;
  legalGuardianName: string;
  legalGuardianLastName: string;
  legalGuardianEmail: string;
  registeredAt: Date;
  paidAt: Date;
  status: string;
  isLateEntry: number;
  studentPayments: StudentPayment[];
  startTime: string;
  venueName: string;
  venueAddress: string;
};

export type PdfFile = {
  candidateNumber: string;
  candidateName: string;
  dateOfBirth: string;
  internalId: string;
  centreNumber: string;
  centreName: string;
  timetable: {
    date: string;
    time: string;
    paper: string;
    venue: string;
    room: number;
  }[];
  venueAddress: string;
  resultsAvailableBy: string;
  registrationUrl: string;
  idNumber: string;
  secretNumber: string;
  contactInfo: {
    name: string;
    organization: string;
    address: string;
    phone: string;
    mobile: string;
    email: string;
  };
};
export type VenueRoom = {
  id: number;
  venue: Venue;
  examType: string;
  capacity: number;
  parCode: string;
};
export type Examiner = {
  id: number;
  name: string;
  email: string;
  rfc: string;
  supervisor: number;
  examiner: number;
  invigilator: number;
  usher: number;
  site: string;
};
export type Venue = {
  id: number;
  cct: number;
  leads: Lead[];
  sessions: VenueSession[];
  rooms: VenueRoom[];
  alias: string;
  address: LeadAddress;
  site: string;

  ////
  status: string;
  externalCandidateSize: number;
  collegeHelp: number;
  helpIn: string;
  accessDistance: string;
  externalNoise: string;
  disabledRamps: string;
  bathroomsStudents: number;
  bathroomsTeachers: number;
  sameOrDifferent: string;
  storageArea: string;
  generalWaitingArea: string;
  speakingWaitingArea: string;
  externalCoordinatorsWaitingArea: string;
  classroomsWithWindows: string; // "Si" | "No"
  outsideView: string; // Ventana | Puerta | ...
  boardType: string; // Blanco | Digital | ...
  usbAudioEquipment: string;
  equipmentCount: number;
  clockCount: number;
  wifi: string; // Si | No
  speakersPhonesCameras: string;
  postersAndSheets: string;
  candidateRangePerClassroom: string;
  oralExamClassrooms: number;
  writtenExamClassrooms: number;
  distributionByFloor: string;
  distributionByBuilding: string;
  distributionCharacteristics: string;
  accesoStaff: string; // Si | No
  datosAccesoStaff: string;
  tiempoAnticipacionStaff: string;
  idRequeridaStaff: string;
  accesoCoordinadores: string; // Si | No
  datosAccesoCoordinadores: string;
  tiempoAnticipacionCoordinadores: string;
  idRequeridaCoordinadores: string;
  estacionamiento: string; // Si | No
  lugaresDisponibles: string;
  datosAccesoEstacionamiento: string;
  tiempoAnticipacionEstacionamiento: string;
  cbExams: string; // Si | No
  laboratorioComputo: string; // Si | No
  equiposComputo: string; // cantidad
  aceptaRevision: string; // Si | No
  fechaRevisionLaboratorio: string; // date
};
export type Payroll = {
  id: number;
  examiner: Examiner;
  payrollCartProduct: CartProduct;
  position: string;
  venueSession: VenueSession;
  paymentType: string;
  totalpaymx: number;
  totalpayco: number;
  totalpaype: number;
  totalPay: number;
  students: number;
  hours: number;
  quantity: number;
  room: string;
};
export type TimeTable = {
  id: number;
  paper: string;
  timeStart: string;
  timeEnd: string;
  room: string;
  date: string;
};

export type VenueSession = {
  id: number;
  venue: Venue;
  sessionStudents: VenueSessionStudent[];
  testDate: Date;
  createdAt: Date;
  deletedAt: Date | null;
  payrolls: Payroll[];
  cambiosEnRequerimientos: string;
  fechaEnvioCambridge: string;
  guiaEnvioCambridge: string;
  validacionMarks: string;
  fechaLiberacionResultados: string;
  fechaDescargaResultados: string;
  fechaRecepcionResultados: string;
  guiaRecepcionResultados: string;
  fechaNotificacionResultados: string;
  fechaEnvioCertificados: string;
  fechaRecepcionAcuses: string;
};
export type Project = {
  id: number;
  name: string;
  cambridgeCode: string;
  carts: Cart[];
  leads: Lead[];
};
export type VenueSessionStudent = {
  id: number;
  room: VenueSessionRoom;
  session: VenueSession;
  student: Student;
  status: string;
  candidateNumber: string;
  idNumber: string;
  centreNumber: string;
  secretNumber: string;
  timetable: TimeTable[];
};

export type VenueSessionRoom = {
  id: number;
};
