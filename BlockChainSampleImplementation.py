# -*- coding: utf-8 -*-
import hashlib
import json

from textwrap import dedent
from time import time
from uuid import uuid4

from flask import Flask, jsonify, request

"""
★ブロックチェーンのサンプル実装
http://postd.cc/learn-blockchains-by-building-one/

★Blockの構成
各ブロックは、
　インデックス
　タイムスタンプ（UNIX時間）
　トランザクションのリスト
　プルーフ（詳しくは後ほど）
　前のブロックのハッシュ値
を持っています。

★流れ：これであっているはず
1.blockの作成(発掘する)
2.それにトランザクションをひもづける
...最初に戻る
※この解説にはないが、1->2の順にやらないと blockを発掘したときにhash値の値が変わってしまう。
なので、1->1->2みたいな順は良くないのでは？2個目のblockの値がおかしくなる気がする


★プルーフ・オブ・ワークアルゴリズム
このアルゴリズムによって次ぎの新しいブロックがブロックチェーン上に作成されたりマイニングされたりする
このアルゴリズムの目的は以下の様な数字を見つけること
→数字が見つけにくくなければならないが、認証しやすく無ければならない

例：x*yのハッシュ値でyを変更していき、ハッシュ値の末尾が0になるyを見つけるアルゴリズム
※proof:証明、証拠...
つまり、BitCoinの発掘作業があると思うが、それの発掘作業がこの上で言うyを見つける事だと思う(たぶん)
以下の実装では先頭が0000となるような値を探している。

※BitCoinとかはどのようなアルゴリズムなんだろうか？


★合意
ブロックチェーンの一つの目的としては分散化
分散してて、どのように同じチェーンに反映しているのか確認するのか
→矛盾がある場合：別のノードで異なるチェーンを持っている
→よって、ルール決める：最長のチェーンを信頼する
　→自分のチェーンよりも長く、有効な物が見つかったら、置き換える


★API
/transactions/new　でブロックに新しいトランザクションを作成。 
/mine　で新しいブロックをマイニングするようサーバに指示。
/chainで完全なブロックチェーンを返す。
/nodes/register 新しいノード一覧をURL形式で応答
/nodes/resolv でコンセンサスアルゴリズムを実装する。これによって矛盾を解決し、ノードが正しいチェーンを保持することを保証する。

★呼び出し
SENDER=`curl --noproxy 127.0.0.1 http://127.0.0.1:5000/mine  | grep recipient | cut -d ":" -f 2 |cut -d "\"" -f 2`
curl --noproxy 127.0.0.1 -X POST -H "Content-Type: application/json" -d '{"sender": "${SENDER}","recipient": "someone-other-address","amount": 5}' http://127.0.0.1:5000/transactions/new

"""

class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.current_transactions = []

        #ノード一覧の保持用
        self.nodes = set()

        #一番はじめのBlock
        #前のブロックのhash値が1は先頭をあらわすのだと思う
        self.new_block(previous_hash = 1, proof = 100)


    def proof_of_work(self, last_proof):
        """
        プルーフ・オブ・ワークアルゴリズムの実装
        :param last_proof: <int> 前回の発掘した値
        :return: <int> アルゴリズムによって発掘した値
        """

        proof = 0
        #Trueになるまでproofの値をインクリメントする
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    
    @staticmethod
    def valid_proof(last_proof, proof):
        """
        :param last_proof: <int> 前のproof
        :param proof: <int> 現在のproof
        :return: <bool> ＯＫかＮＧか
        """

        #last_proofとproofの結合した文字列を作ってbyteにする
        guess = f'{last_proof}{proof}'.encode()
        #そしてそれをhash
        guess_hash = hashlib.sha256(guess).hexdigest()

        #先頭が0000かどうかのTrue/Falseを返す
        return guess_hash[:4] == "0000"
        

    def new_block(self, proof, previous_hash=None):
        """
        新しいブロックを作成
        :param proof: <int> 
        :param previous_hash: (Optional) <str> 前のBlockのhash値
        :return: <dict> 新しいBlock
        """

        block = {
            'index': len(self.chain) + 1,
            'timestamp':time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
            }

        self.current_transactions = []
        self.chain.append(block)
        return block

    
    def new_transaction(self, sender, recipient, amount):
        """
        ブロックにトランザクションを追加
        :param sender: <str>送信者のアドレス
        :param recipient: <str>受信者のアドレス
        :param amount: <int> 総計？総額？
        :return: <int> 次のblockのindexを返却
        """
        self.current_transactions.append({
            'sender':sender,
            'recipient':recipient,
            'amount':amount,
            })
        
        return self.last_block['index'] + 1

    
    def valid_chain(self, chain):
        """
        chainのチェック。先頭から順次確認していく
        """
        #先頭からチェックしていく
        last_block = chain[0]
        #チェック中のindex
        current_index = 1
        
        #渡されたchain中のblockとインスタンス変数のblockを比較していく
        while current_index < len(chain):

            block = chain[current_index]

            #一個前のblockのハッシュ値(実際に計算)と、現在チェック中のblockに埋め込まれている前blockのhash値の値が正しいかを確認
            if block['previous_hash'] != self.hash(last_block):
                return False

            #proofの値も整合性が取れいているかの確認
            #前ブロックのproofとcurrentの値を渡して確認する
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block

            current_index += 1

        return True


    def rsolv_conflicts(self):
        """
        合意アルゴリズム
        上で書いたように、整合性(valid_chain()でのチェックがOK)で一番長いものを探す
        もしそんな物があればチェーンを置き換える
        """
        #登録済みのご近所さん
        neighbours = self.nodes
        
        new_chain = None

        #このノードが持っているチェーンの長さ
        max_length = len(self.chain)

        #ご近所さんからチェーンの情報を取得して、整合性がとれてて、最長なものを探してくる
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if responsel.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True

        return False
    

    def register_node(self, address):
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

        
    @staticmethod
    def hash(block):
        """
        SHA-256 Hash のブロックの作成
        :param block: <dict> Block
        :return: <str> ハッシュ値
        """
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]


app = Flask(__name__)

#ノードの名前を適当に決定
node_identifier = str(uuid4()).replace('-','')

blockchain = Blockchain()


@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']

    #これが発掘作業なんだと思う
    proof = blockchain.proof_of_work(last_proof)

    blockchain.new_transaction(
        sender = "0",
        recipient = node_identifier,
        amount=1
        )

    
    #新しいblockの作成

    #毎回値が変わるのはtimestampがあるからだな
    previous_hash = blockchain.hash(last_block)
    #前のblockのハッシュ値と発掘した値で新しいblockをつくる
    block = blockchain.new_block(proof, previous_hash)

    response = {
        'message': "New Block",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }

    return jsonify(response),200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    #必要なパラメータがPOSTされているかチェック
    required = ['sender','recipient','amount']
    if not all(k in values for k in required):
        return "値が不足している", 400

    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response = {'message': f'ブロックに追加したよ {index}'}

    return jsonify(response), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
        }
    return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')

    if nodes is None:
        return "何も無いよ"

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': '新しいご近所さんが追加されました',
        'total_nodes': list(blockchain.nodes),
    }

    return jsonify(response),201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.rsolv_conflicts()

    if replaced:
        response = {
            'message':'変更されました',
            'new_chain':blockchain.chain,
        }
    else:
        response = {
            'message':'自身のchainはいけてます',
            'chain':blockchain.chain,
        }

    return jsonify(response), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
