import os
import json
import random
import time
from transformers import AutoModelForCausalLM, AutoTokenizer

class AIChat:
    def __init__(self, model_path=None):
        self.tokenizer = None
        self.model = None
        self.conversation_history = []
        self.max_history = 10  # 대화 히스토리 최대 길이
        
        # 기본 응답 템플릿
        self.default_responses = [
            "안녕하세요! 무엇을 도와드릴까요?",
            "반갑습니다! 질문이 있으신가요?",
            "집 안에서 도움이 필요하신가요?",
            "네, 말씀하세요!",
            "무엇을 알려드릴까요?"
        ]
        
        # 기본 질문-응답 데이터셋
        self.qa_dataset = self._load_qa_dataset()
        
        # 모델 로드 시도
        self._load_model(model_path)
    
    def _load_model(self, model_path):
        """AI 모델 로드"""
        try:
            if model_path:
                print(f"사용자 지정 모델 로드 중: {model_path}")
            else:
                # 다음과 같은 한국어 LLM 모델을 사용할 수 있음
                # beomi/KoAlpaca-1.1b, kyujinpy/KoT5-large 등
                model_path = "beomi/KoAlpaca-1.1b"
                print(f"기본 모델 로드 중: {model_path}")
            
            # 실제 구현 시 주석 해제 (메모리 필요)
            # self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            # self.model = AutoModelForCausalLM.from_pretrained(model_path)
            # print("모델 로드 완료")
            
            # 저사양 환경을 위한 우회 코드
            print("모델 로딩을 건너뛰고 기본 응답 사용 (테스트 모드)")
        except Exception as e:
            print(f"모델 로드 실패: {e}")
            print("기본 응답을 사용합니다.")
    
    def _load_qa_dataset(self):
        """질문-응답 데이터셋 로드"""
        qa_dataset = {
            "누구야": ["저는 홈캠 AI 도우미입니다.", "당신의 홈캠 도우미입니다."],
            "날씨": ["현재 날씨 정보는 제공하지 않습니다.", "날씨 정보는 확인할 수 없어요."],
            "시간": ["현재 시간은 {}입니다.".format(time.strftime("%H시 %M분", time.localtime()))],
            "안녕": ["안녕하세요!", "반갑습니다!", "어서오세요!"],
            "도움": ["네, 어떤 도움이 필요하신가요?", "무엇을 도와드릴까요?"],
            "기능": ["카메라 화면 보기, 사진 촬영, 음성 대화 기능이 있습니다."]
        }
        
        # 추가 데이터셋 파일이 있다면 로드
        dataset_path = os.path.join('models', 'qa_dataset.json')
        if os.path.exists(dataset_path):
            try:
                with open(dataset_path, 'r', encoding='utf-8') as f:
                    additional_dataset = json.load(f)
                    # 기존 데이터셋에 추가
                    for key, value in additional_dataset.items():
                        qa_dataset[key] = value
            except Exception as e:
                print(f"데이터셋 로드 실패: {e}")
        
        return qa_dataset
    
    def get_response(self, message):
        """메시지에 대한 응답 생성"""
        if not message.strip():
            return random.choice(self.default_responses)
        
        # 대화 히스토리 업데이트
        self.conversation_history.append({"role": "user", "message": message})
        
        # 히스토리 제한
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]
        
        # 모델로 응답 생성 시도
        response = self._generate_model_response(message)
        
        # 응답이 없으면 키워드 기반 응답 시도
        if not response:
            response = self._get_keyword_response(message)
        
        # 대화 히스토리에 응답 추가
        self.conversation_history.append({"role": "assistant", "message": response})
        
        return response
    
    def _generate_model_response(self, message):
        """AI 모델을 사용하여 응답 생성"""
        if not self.model or not self.tokenizer:
            return ""
        
        try:
            # 대화 히스토리를 고려한 프롬프트 생성
            prompt = self._create_prompt_from_history()
            
            # 모델에 입력하여 응답 생성
            inputs = self.tokenizer(prompt, return_tensors="pt")
            outputs = self.model.generate(
                inputs.input_ids, 
                max_length=100, 
                do_sample=True, 
                top_p=0.92, 
                temperature=0.8
            )
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # 프롬프트 제거하여 실제 응답만 추출
            response = response.replace(prompt, "").strip()
            
            return response
        except Exception as e:
            print(f"모델 응답 생성 실패: {e}")
            return ""
    
    def _create_prompt_from_history(self):
        """대화 히스토리를 기반으로 프롬프트 생성"""
        prompt = "다음은 홈캠 AI 도우미와 사용자 간의 대화입니다.\n\n"
        
        for entry in self.conversation_history[-5:]:  # 최근 5개 대화만 사용
            role = "사용자" if entry["role"] == "user" else "홈캠"
            prompt += f"{role}: {entry['message']}\n"
        
        prompt += "홈캠: "
        return prompt
    
    def _get_keyword_response(self, message):
        """키워드 기반 응답 생성"""
        # 메시지에서 키워드 추출
        message_lower = message.lower()
        
        # 데이터셋에서 일치하는 키워드 찾기
        for keyword, responses in self.qa_dataset.items():
            if keyword in message_lower:
                return random.choice(responses)
        
        # 일치하는 키워드가 없으면 기본 응답
        return random.choice(self.default_responses)
    
    def clear_history(self):
        """대화 히스토리 초기화"""
        self.conversation_history = []
        return True 