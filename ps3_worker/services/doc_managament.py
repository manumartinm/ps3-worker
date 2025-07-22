import base64
import io
import os
import shutil

import fitz
from PIL import Image
from pdf2image import convert_from_path
from langchain_community.embeddings import HuggingFaceEmbeddings


class DocManagament:
    def __init__(self, pdf_base64, temp_filename=None):
        # Generar hash único para el PDF
        self.pdf_hash = self._generate_hash(pdf_base64)

        if not os.path.exists("data"):
            os.makedirs("data")

        self.data_dir = os.path.join("data", self.pdf_hash)
        os.makedirs(self.data_dir, exist_ok=True)
        if temp_filename is None:
            temp_filename = f"{self.pdf_hash}.pdf"
        try:
            self.pdf_path = self._save_base64_to_pdf(
                pdf_base64, os.path.join(self.data_dir, temp_filename)
            )
        except Exception as e:
            raise ValueError(f"Error al decodificar y guardar el PDF: {e}")

        # pyrefly: ignore  # missing-attribute, bad-argument-type
        self.path = self.pdf_path.replace(".pdf", "")
        self.document = None
        self.raw_text = None
        self.n_pages = None

        print(f"Objeto DocManagament creado para el archivo: {self.pdf_path}")
        print("Intentando extraer texto crudo del PDF...")

        try:
            self.convert_pdf_to_grayscale(self.pdf_path, f"{self.path}_normalized.pdf")
            # pyrefly: ignore  # bad-assignment
            self.raw_text = self.extract_text(self.pdf_path)

            if self.raw_text:
                print("Texto crudo extraído exitosamente.")
            else:
                print("Advertencia: Texto crudo extraído está vacío.")
        except Exception as e:
            print(f"Error al extraer texto crudo del PDF: {e}")
            print("Las operaciones de chunking no estarán disponibles.")

    def _generate_hash(self, pdf_base64):
        return (
            base64.urlsafe_b64encode(
                (
                    base64.b64encode(pdf_base64.encode("utf-8"))
                    if isinstance(pdf_base64, str)
                    else pdf_base64
                )[:16]
            )
            .decode("utf-8")
            .replace("=", "")
        )

    def _save_base64_to_pdf(self, pdf_base64, filename):
        decoded_data = base64.b64decode(pdf_base64)
        path = os.path.abspath(filename)
        with open(path, "wb") as f:
            f.write(decoded_data)
        return path

    def extract_text(self, input_pdf):
        doc = fitz.open(input_pdf)
        final_text = ""
        for page in doc:
            final_text += "\n" + page.get_text()
        doc.close()
        return final_text

    def convert_pdf_to_grayscale(self, input_pdf_path, output_pdf_path, dpi=200):
        pdf_document = fitz.open(input_pdf_path)
        new_pdf = fitz.open()

        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            matrix = fitz.Matrix(dpi / 72, dpi / 72)
            # pyrefly: ignore  # missing-attribute
            pix = page.get_pixmap(matrix=matrix)

            # pyrefly: ignore  # bad-argument-type
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            grayscale_img = img.convert("L")
            img_byte_arr = io.BytesIO()
            grayscale_img.save(img_byte_arr, format="PNG")

            # pyrefly: ignore  # missing-attribute
            new_page = new_pdf.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, stream=img_byte_arr.getvalue())

        new_pdf.save(output_pdf_path)
        new_pdf.close()
        pdf_document.close()
        print(f"PDF convertido a escala de grises y guardado en: {output_pdf_path}")

    def to_jpgs(self, output_dir=None):
        try:
            if output_dir is None:
                output_dir = self.data_dir
            os.makedirs(output_dir, exist_ok=True)
            print(f"Convirtiendo '{self.pdf_path}' a JPGs en '{output_dir}'...")

            # pyrefly: ignore  # bad-argument-type
            images = convert_from_path(
                self.pdf_path, poppler_path=r"C:\Program Files\Poppler\Library\bin"
            )
            for i, image in enumerate(images):
                jpg_path = os.path.join(output_dir, f"page_{i+1}.jpg")
                image.save(jpg_path, "JPEG")

            self.n_pages = len(images)  # type: ignore

            print(
                f"Se han guardado {self.n_pages} páginas como archivos JPG en '{output_dir}'."
            )
        except Exception as e:
            print(f"Ocurrió un error durante la conversión a JPGs: {e}")

    def to_chunks(self):
        if not self.raw_text:
            print(
                "No se puede realizar el chunking: El texto crudo del PDF no está disponible."
            )
            return None

        print("Realizando chunking semántico del texto...")
        try:
            model_name = "NeuML/bioclinical-modernbert-base-embeddings"
            encode_kwargs = {"normalize_embeddings": True}

            hf_embeddings = HuggingFaceEmbeddings(
                model_name=model_name, encode_kwargs=encode_kwargs
            )

            # pyrefly: ignore  # unknown-name
            text_splitter = SemanticChunker(hf_embeddings)
            docs_chunks = text_splitter.create_documents([self.raw_text])

            print(
                f"Chunking completado. Generados {len(docs_chunks)} fragmentos semánticos."
            )
            return docs_chunks
        except Exception as e:
            print(f"Ocurrió un error durante el chunking semántico: {e}")
            return None

    def remove_data_dir(self):
        try:
            if os.path.exists(self.data_dir):
                shutil.rmtree(self.data_dir)
                print(f"Carpeta '{self.data_dir}' eliminada correctamente.")
            else:
                print(f"La carpeta '{self.data_dir}' no existe.")
        except Exception as e:
            print(f"Error al eliminar la carpeta '{self.data_dir}': {e}")
